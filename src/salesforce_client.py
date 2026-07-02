import json

import httpx

from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

logger = getLogger()

SALESFORCE_DEFAULT_TIMEOUT = 30
SALESFORCE_API_FALLBACK_VERSION = "/services/data/v59.0"


class SalesforceClient:
    def __init__(self, asset) -> None:
        self._asset = asset

    def _access_token(self) -> str:
        token = self._asset.auth_state.get("access_token")
        if not token:
            raise ActionFailure("No access token found. Re-run test connectivity.")
        return token

    def _instance_url(self) -> str:
        url = self._asset.auth_state.get("instance_url")
        if not url:
            raise ActionFailure("No instance URL found. Re-run test connectivity.")
        return url

    def _api_version(self) -> str:
        return self._asset.cache_state.get("latest_version", SALESFORCE_API_FALLBACK_VERSION)

    def _base_url(self) -> str:
        return f"{self._instance_url()}{self._api_version()}"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._access_token()}"}

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self._base_url()}{path}"
        resp = httpx.request(
            method, url,
            headers=self._headers(),
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
            **kwargs,
        )
        if not resp.is_success:
            try:
                errors = resp.json()
                msg = errors[0].get("message", resp.text) if isinstance(errors, list) else resp.text
            except Exception:
                msg = resp.text
            raise ActionFailure(f"Salesforce API error {resp.status_code}: {msg}")
        return {} if resp.status_code == 204 else resp.json()


    def query(self, soql: str, endpoint: str = "query") -> list[dict]:
        """Execute a SOQL query and return all records (auto-paginates)."""
        data = self._request("GET", f"/{endpoint}", params={"q": soql})
        records = data.get("records", [])
        next_url = data.get("nextRecordsUrl")
        while next_url:
            # nextRecordsUrl is an absolute path like /services/data/vXX.0/query/...
            resp = httpx.get(
                f"{self._instance_url()}{next_url}",
                headers=self._headers(),
                timeout=SALESFORCE_DEFAULT_TIMEOUT,
                verify=False,  # noqa: S501
            )
            resp.raise_for_status()
            page = resp.json()
            records.extend(page.get("records", []))
            next_url = page.get("nextRecordsUrl")
        return records


    def create(self, sobject: str, fields: dict) -> dict:
        """Create a new sObject record. Returns {id, success}."""
        return self._request("POST", f"/sobjects/{sobject}", json=fields)

    def get(self, sobject: str, record_id: str) -> dict:
        """Fetch a single sObject record by ID."""
        return self._request("GET", f"/sobjects/{sobject}/{record_id}")

    def update(self, sobject: str, record_id: str, fields: dict) -> None:
        """Patch an existing sObject record (returns nothing on 204)."""
        self._request("PATCH", f"/sobjects/{sobject}/{record_id}", json=fields)

    def delete(self, sobject: str, record_id: str) -> None:
        """Delete a sObject record (returns nothing on 204)."""
        self._request("DELETE", f"/sobjects/{sobject}/{record_id}")


    def batch_get(self, sobject: str, record_ids: list[str]) -> list[dict]:
        """Fetch up to 25 sObject records in a single batch request."""
        version = self._api_version()
        requests = [
            {"method": "GET", "url": f"{version}/sobjects/{sobject}/{rid}"}
            for rid in record_ids
        ]
        data = self._request("POST", "/composite/batch", json={"batchRequests": requests})
        results = []
        for item in data.get("results", []):
            if item.get("statusCode") == 200:
                results.append(item["result"])
        return results

    def list_view_records_paged(
        self,
        sobject: str,
        view_name: str,
        offset: int = 0,
        max_records: int | None = None,
    ) -> tuple[int, list[dict]]:
        """Fetch list-view summary records sorted by LastModifiedDate.

        Returns (new_offset, records) where records are the raw list-view row dicts.
        """
        MAX_PER_PAGE = 2000
        view_id = self.resolve_list_view_id(sobject, view_name)
        records: list[dict] = []

        while True:
            params: dict = {"sortBy": "LastModifiedDate", "pageSize": MAX_PER_PAGE, "pageToken": offset}
            data = self._request("GET", f"/sobjects/{sobject}/listviews/{view_id}/results", params=params)
            page = data.get("records", [])
            records.extend(page)

            if max_records and len(records) >= max_records:
                records = records[:max_records]
                offset += len(records)
                break

            if len(page) < MAX_PER_PAGE:
                offset += len(page)
                break

            offset += MAX_PER_PAGE

        return offset, records

    def list_views(self, sobject: str) -> list[dict]:
        """Return all list views for a given sObject."""
        data = self._request("GET", f"/sobjects/{sobject}/listviews")
        return data.get("listviews", [])

    def list_view_results(
        self,
        sobject: str,
        list_view_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict:
        """Return the results of a specific list view."""
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._request("GET", f"/sobjects/{sobject}/listviews/{list_view_id}/results", params=params)

    def resolve_list_view_id(self, sobject: str, view_name: str) -> str:
        """Resolve a developer name or label to a list view ID. Raises ActionFailure if not found."""
        views = self.list_views(sobject)
        name_lower = view_name.lower()
        for v in views:
            if v.get("developerName", "").lower() == name_lower or v.get("label", "").lower() == name_lower:
                return v["id"]
        available = ", ".join(v.get("developerName", v.get("label", "")) for v in views)
        raise ActionFailure(f"List view '{view_name}' not found for {sobject}. Available: {available}")


    def post_chatter(self, case_id: str, body: str, title: str | None = None) -> dict:
        """Post a text message to the Chatter feed of a Case."""
        text = f"{title}\n\n{body}" if title else body
        segments = [{"type": "Text", "text": text}]
        payload: dict = {
            "body": {"messageSegments": segments},
            "feedElementType": "FeedItem",
            "subjectId": case_id,
        }

        # Chatter Feed Elements endpoint lives outside the versioned data path
        url = f"{self._instance_url()}{self._api_version()}/chatter/feed-elements"
        resp = httpx.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            content=json.dumps(payload),
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        if not resp.is_success:
            try:
                errors = resp.json()
                msg = errors[0].get("message", resp.text) if isinstance(errors, list) else resp.text
            except Exception:
                msg = resp.text
            raise ActionFailure(f"Chatter post failed {resp.status_code}: {msg}")
        data = resp.json()
        return {"id": data.get("id", ""), "success": True}
