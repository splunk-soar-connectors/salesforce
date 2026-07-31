# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import json
from urllib.parse import quote

import httpx

from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from .auth import get_instance_url, get_request_auth

logger = getLogger()

SALESFORCE_DEFAULT_TIMEOUT = 30
SALESFORCE_API_FALLBACK_VERSION = "/services/data/v59.0"
MAX_OBJECTS_PER_POLL_PAGE = 2000
MAX_PAGES_PER_POLL = 100


class SalesforceClient:
    def __init__(self, asset) -> None:
        self._asset = asset

    def _instance_url(self) -> str:
        return get_instance_url(self._asset)

    def _api_version(self) -> str:
        return self._asset.cache_state.get(
            "latest_version", SALESFORCE_API_FALLBACK_VERSION
        )

    def _base_url(self) -> str:
        return f"{self._instance_url()}{self._api_version()}"

    def _verify_ssl(self) -> bool:
        return bool(self._asset.verify_ssl)

    @staticmethod
    def _validate_path_segment(value: str, key: str) -> None:
        """Raise ActionFailure if value contains characters that can escape a URL path segment."""
        if (
            not isinstance(value, str)
            or any(c in value for c in ("/", "\\", "?", "#"))
            or ".." in value
        ):
            raise ActionFailure(
                f"Invalid value for '{key}': must be a single Salesforce path segment"
            )

    def _request(self, method: str, path: str, **kwargs) -> dict:
        auth = get_request_auth(self._asset)
        url = f"{self._base_url()}{path}"
        resp = httpx.request(
            method,
            url,
            auth=auth,
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=self._verify_ssl(),
            **kwargs,
        )
        if not resp.is_success:
            try:
                errors = resp.json()
                msg = (
                    errors[0].get("message", resp.text)
                    if isinstance(errors, list)
                    else resp.text
                )
            except Exception:
                msg = resp.text
            raise ActionFailure(f"Salesforce API error {resp.status_code}: {msg}")
        return {} if resp.status_code == 204 else resp.json()

    def _request_absolute(self, path: str) -> dict:
        """Issue a GET to an absolute instance-relative path (e.g. nextRecordsUrl)."""
        auth = get_request_auth(self._asset)
        url = f"{self._instance_url()}{path}"
        resp = httpx.get(
            url,
            auth=auth,
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=self._verify_ssl(),
        )
        if not resp.is_success:
            try:
                errors = resp.json()
                msg = (
                    errors[0].get("message", resp.text)
                    if isinstance(errors, list)
                    else resp.text
                )
            except Exception:
                msg = resp.text
            raise ActionFailure(f"Salesforce API error {resp.status_code}: {msg}")
        return resp.json()

    def query(self, soql: str, endpoint: str = "query") -> list[dict]:
        """Execute a SOQL query and return all records (auto-paginates)."""
        data = self._request("GET", f"/{endpoint}", params={"q": soql})
        records = data.get("records", [])
        next_url = data.get("nextRecordsUrl")
        while next_url:
            # nextRecordsUrl is an absolute path like /services/data/vXX.0/query/...
            page = self._request_absolute(next_url)
            records.extend(page.get("records", []))
            next_url = page.get("nextRecordsUrl")
        return records

    def create(self, sobject: str, fields: dict) -> dict:
        """Create a new sObject record. Returns {id, success}."""
        self._validate_path_segment(sobject, "sobject")
        return self._request(
            "POST", f"/sobjects/{quote(sobject, safe='')}", json=fields
        )

    def get(self, sobject: str, record_id: str) -> dict:
        """Fetch a single sObject record by ID."""
        self._validate_path_segment(sobject, "sobject")
        self._validate_path_segment(record_id, "id")
        return self._request(
            "GET", f"/sobjects/{quote(sobject, safe='')}/{quote(record_id, safe='')}"
        )

    def update(self, sobject: str, record_id: str, fields: dict) -> None:
        """Patch an existing sObject record (returns nothing on 204)."""
        self._validate_path_segment(sobject, "sobject")
        self._validate_path_segment(record_id, "id")
        self._request(
            "PATCH",
            f"/sobjects/{quote(sobject, safe='')}/{quote(record_id, safe='')}",
            json=fields,
        )

    def delete(self, sobject: str, record_id: str) -> None:
        """Delete a sObject record (returns nothing on 204)."""
        self._validate_path_segment(sobject, "sobject")
        self._validate_path_segment(record_id, "id")
        self._request(
            "DELETE", f"/sobjects/{quote(sobject, safe='')}/{quote(record_id, safe='')}"
        )

    def batch_get(
        self, sobject: str, record_ids: list[str]
    ) -> tuple[list[dict], list[str]]:
        """Fetch up to 25 sObject records in a single batch request.

        Returns (records, failed_ids) — failed_ids are IDs whose per-item status was not 200.
        """
        self._validate_path_segment(sobject, "sobject")
        for rid in record_ids:
            self._validate_path_segment(rid, "id")
        version = self._api_version()
        s = quote(sobject, safe="")
        id_list = list(record_ids)
        batch_requests = [
            {"method": "GET", "url": f"{version}/sobjects/{s}/{quote(rid, safe='')}"}
            for rid in id_list
        ]
        data = self._request(
            "POST", "/composite/batch", json={"batchRequests": batch_requests}
        )
        records = []
        failed_ids = []
        for rid, item in zip(id_list, data.get("results", []), strict=False):
            if item.get("statusCode") == 200:
                records.append(item["result"])
            else:
                logger.warning(
                    f"Batch fetch failed for {sobject}/{rid}: "
                    f"status={item.get('statusCode')} result={item.get('result')}"
                )
                failed_ids.append(rid)
        return records, failed_ids

    def list_view_records_paged(
        self,
        sobject: str,
        view_name: str,
        offset: int = 0,
        max_records: int | None = None,
    ) -> tuple[int, list[dict]]:
        """Fetch list-view summary records using limit/offset pagination.

        Returns (new_offset, records) where records are the raw list-view row dicts.
        """
        view_id = self.resolve_list_view_id(sobject, view_name)
        records: list[dict] = []

        for _page_number in range(MAX_PAGES_PER_POLL):
            page_size = MAX_OBJECTS_PER_POLL_PAGE
            if max_records is not None:
                remaining = max_records - len(records)
                if remaining <= 0:
                    break
                page_size = min(MAX_OBJECTS_PER_POLL_PAGE, remaining)

            params: dict = {"limit": page_size, "offset": offset}
            data = self._request(
                "GET",
                f"/sobjects/{quote(sobject, safe='')}/listviews/{quote(view_id, safe='')}/results",
                params=params,
            )
            page = data.get("records", [])
            records.extend(page)
            offset += len(page)

            if max_records is not None and len(records) >= max_records:
                records = records[:max_records]
                break

            if len(page) < page_size:
                break
        else:
            logger.info(
                f"Reached the maximum of {MAX_PAGES_PER_POLL} pages in one poll cycle"
            )

        return offset, records

    def list_views(self, sobject: str) -> list[dict]:
        """Return all list views for a given sObject."""
        self._validate_path_segment(sobject, "sobject")
        data = self._request("GET", f"/sobjects/{quote(sobject, safe='')}/listviews")
        return data.get("listviews", [])

    def list_view_results(
        self,
        sobject: str,
        list_view_id: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict:
        """Return the results of a specific list view."""
        self._validate_path_segment(sobject, "sobject")
        self._validate_path_segment(list_view_id, "list_view_id")
        params = {}
        if limit is not None:
            params["limit"] = limit
        if offset is not None:
            params["offset"] = offset
        return self._request(
            "GET",
            f"/sobjects/{quote(sobject, safe='')}/listviews/{quote(list_view_id, safe='')}/results",
            params=params,
        )

    def resolve_list_view_id(self, sobject: str, view_name: str) -> str:
        """Resolve a developer name or label to a list view ID. Case-sensitive. Raises ActionFailure if not found."""
        views = self.list_views(sobject)
        for v in views:
            if v.get("developerName") == view_name or v.get("label") == view_name:
                return v["id"]
        available = ", ".join(v.get("developerName", v.get("label", "")) for v in views)
        raise ActionFailure(
            f"List view '{view_name}' not found for {sobject}. Available: {available}"
        )

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
            auth=get_request_auth(self._asset),
            headers={"Content-Type": "application/json"},
            content=json.dumps(payload),
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=self._verify_ssl(),
        )
        if not resp.is_success:
            try:
                errors = resp.json()
                msg = (
                    errors[0].get("message", resp.text)
                    if isinstance(errors, list)
                    else resp.text
                )
            except Exception:
                msg = resp.text
            raise ActionFailure(f"Chatter post failed {resp.status_code}: {msg}")
        return resp.json()
