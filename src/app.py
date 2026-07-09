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
import base64
import hashlib
import json
import secrets
import time
from collections.abc import Iterator
from urllib.parse import urlencode

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

from .actions import register_actions
from .asset import Asset
from .salesforce_client import SalesforceClient

logger = getLogger()

SALESFORCE_PKCE_VERIFIER_BYTES = 96
SALESFORCE_DEFAULT_TIMEOUT = 30

URL_GET_CODE = "https://login.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN = "https://login.salesforce.com/services/oauth2/token"  # noqa: S105
URL_GET_CODE_TEST = "https://test.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN_TEST = "https://test.salesforce.com/services/oauth2/token"  # noqa: S105

SEVERITY_MAP = {
    "severity 1 (high impact)": "high",
    "severity 2 (medium impact)": "medium",
    "severity 3 (low impact)": "low",
    "severity 4 (false positive)": "low",
}
SENSITIVITY_MAP = {
    "sensitive": "red",
    "not sensitive": "white",
}


def _extract_id_from_record(r: dict) -> str:
    for col in r.get("columns", []):
        if col.get("fieldNameOrPath") == "Id":
            return col.get("value", "")
    return r.get("fields", {}).get("Id", {}).get("value", "")


def create_salesforce_soar_connector_app() -> App:
    app = App(
        name="Salesforce",
        app_type="ticketing",
        logo="logo_salesforce.svg",
        logo_dark="logo_salesforce_dark.svg",
        product_vendor="Salesforce",
        product_name="Salesforce",
        publisher="Splunk",
        appid="6c1316b0-88a7-4864-b684-3170f6c455be",
        fips_compliant=True,
        asset_cls=Asset,
    ).enable_webhooks(default_requires_auth=False)

    @app.webhook("/redirect", allowed_methods=["GET"])
    def handle_redirect(request: WebhookRequest) -> WebhookResponse:
        """Bounces the browser to the Salesforce authorization URL stored in auth_state."""
        asset: Asset = request.asset
        url = asset.auth_state.get("url")
        if not url:
            return WebhookResponse.text_response(
                "ERROR: No authorization URL found. Re-run test connectivity.",
                status_code=400,
            )
        return WebhookResponse(status_code=302, content="", headers=[("Location", url)])

    @app.webhook("/start_oauth", allowed_methods=["GET"])
    def handle_start_oauth(request: WebhookRequest) -> WebhookResponse:
        """Receives the OAuth callback from Salesforce, exchanges the code for a refresh token."""
        asset: Asset = request.asset
        auth_state = asset.auth_state

        code = (request.query.get("code") or [""])[0]
        if not code:
            error = (
                request.query.get("error_description")
                or request.query.get("error")
                or ["Unknown error"]
            )[0]
            auth_state["error"] = True
            return WebhookResponse.text_response(
                f"Authentication failed: {error}", status_code=401
            )

        url_get_token = auth_state.get("url_get_token")
        if not url_get_token:
            auth_state["error"] = True
            return WebhookResponse.text_response(
                "ERROR: State missing token URL. Re-run test connectivity.",
                status_code=400,
            )

        token_body = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": auth_state["client_id"],
            "redirect_uri": auth_state["redirect_uri"],
            "client_secret": auth_state["client_secret"],
            "code_verifier": auth_state["code_verifier"],
        }

        try:
            r = httpx.post(
                url_get_token,
                data=token_body,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=SALESFORCE_DEFAULT_TIMEOUT,
                verify=False,  # noqa: S501
            )
            resp_json = r.json()
        except Exception as e:
            auth_state["error"] = True
            return WebhookResponse.text_response(
                f"Error retrieving OAuth token: {e}", status_code=401
            )

        sf_error = resp_json.get("error_description") or resp_json.get("error")
        if sf_error:
            auth_state["error"] = True
            return WebhookResponse.text_response(
                f"Salesforce token exchange failed: {sf_error}", status_code=401
            )

        refresh_token = resp_json.get("refresh_token")
        if not refresh_token:
            auth_state["error"] = True
            return WebhookResponse.text_response(
                "Unable to retrieve refresh token. Check OAuth scopes include refresh_token.",
                status_code=401,
            )

        auth_state["refresh_token"] = refresh_token
        auth_state.pop("url", None)
        auth_state.pop("url_get_token", None)
        auth_state.pop("client_id", None)
        auth_state.pop("client_secret", None)
        auth_state.pop("redirect_uri", None)
        auth_state.pop("code_verifier", None)
        auth_state.pop("error", None)

        return WebhookResponse.text_response("You can now close this page.")

    @app.on_poll()
    def on_poll(
        params: OnPollParams, soar: SOARClient, asset: Asset
    ) -> Iterator[Container | Artifact]:
        sobject = asset.poll_sobject or "Case"
        view_name = asset.poll_view_name
        include_view_date = (
            asset.last_view_date if asset.last_view_date is not None else True
        )
        container_label: str | None = (
            app.actions_manager.get_config().get("ingest", {}).get("container_label")
        )

        if not view_name:
            raise ActionFailure("poll_view_name must be set in asset configuration.")

        cef_name_map: dict[str, str] = {}
        if asset.cef_name_map:
            try:
                cef_name_map = json.loads(asset.cef_name_map)
            except (json.JSONDecodeError, TypeError) as e:
                raise ActionFailure(f"cef_name_map is not valid JSON: {e}") from e
            for k, v in cef_name_map.items():
                if not isinstance(v, str) or not k.strip() or not v.strip():
                    raise ActionFailure(
                        "cef_name_map must contain non-empty string keys and values."
                    )

        is_manual = params.is_manual_poll()

        if is_manual:
            offset = 0
            max_records = int(params.container_count) if params.container_count else 10
        else:
            offset = int(asset.ingest_state.get("cur_offset") or 0)
            max_records = None
            if offset == 0:
                max_records = int(asset.first_ingestion_max or 10)

        logger.info(
            f"Polling {sobject} list view '{view_name}' from offset {offset}, max={max_records}"
        )

        client = SalesforceClient(asset)
        new_offset, list_records = client.list_view_records_paged(
            sobject, view_name, offset=offset, max_records=max_records
        )

        logger.info(
            f"Fetched {len(list_records)} list-view records from '{view_name}' (offset={offset}, max={max_records}); container_label={container_label!r}"
        )

        if not list_records:
            logger.info("No new records found.")
            if not is_manual:
                asset.ingest_state["cur_offset"] = new_offset
            return

        record_ids = [
            _id for row in list_records if (_id := _extract_id_from_record(row))
        ]

        logger.info(f"Extracted {len(record_ids)} record IDs from list-view rows")

        full_records: list[dict] = []
        for i in range(0, len(record_ids), 25):
            batch = client.batch_get(sobject, record_ids[i : i + 25])
            full_records.extend(batch)

        logger.info(f"Fetched {len(full_records)} full {sobject} records")

        for record in full_records:
            cef: dict = {}
            cef_types: dict = {}

            for k, v in record.items():
                if k == "attributes":
                    continue
                cef_key = cef_name_map.get(k, k)
                cef[cef_key] = v
                if k.endswith("Id") and v is not None:
                    cef_types[cef_key] = ["salesforce object id"]

            if not include_view_date:
                cef.pop("LastViewedDate", None)
                cef.pop("LastReferencedDate", None)

            container_name = (
                record.get("Subject")
                or f"Salesforce {sobject} # {record.get('CaseNumber') or record.get('Id', '')}"
            )

            record_id = record.get("Id", "")
            container_sdi = hashlib.sha256(f"{sobject}{record_id}".encode()).hexdigest()
            artifact_sdi = hashlib.sha256(
                json.dumps(cef, sort_keys=True).encode()
            ).hexdigest()

            container = Container(
                name=container_name,
                label=container_label,
                source_data_identifier=container_sdi,
                severity=SEVERITY_MAP.get(
                    (record.get("Incident_Severity__c") or "").lower()
                ),
                sensitivity=SENSITIVITY_MAP.get(
                    (record.get("Incident_Sensitivity__c") or "").lower()
                ),
            )
            yield container

            yield Artifact(
                name=sobject,
                label="event",
                source_data_identifier=artifact_sdi,
                cef=cef,
                cef_types=cef_types if cef_types else None,
            )

        if not is_manual:
            asset.ingest_state["cur_offset"] = new_offset
            logger.info(f"Saved poll offset: {new_offset}")

    def _test_connectivity_oauth(asset: Asset) -> None:
        """Browser-based OAuth with PKCE flow."""
        code_verifier = (
            base64.urlsafe_b64encode(
                secrets.token_bytes(SALESFORCE_PKCE_VERIFIER_BYTES)
            )
            .rstrip(b"=")
            .decode()
        )
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode("ascii")).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        redirect_uri = app.get_webhook_url("start_oauth")

        if asset.is_test_environment:
            url_get_code = URL_GET_CODE_TEST
            url_get_token = URL_GET_TOKEN_TEST
        else:
            url_get_code = URL_GET_CODE
            url_get_token = URL_GET_TOKEN

        auth_params = {
            "response_type": "code",
            "client_id": asset.client_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        full_auth_url = f"{url_get_code}?{urlencode(auth_params)}"

        auth_state = asset.auth_state
        auth_state.put_all(
            {
                "url": full_auth_url,
                "url_get_token": url_get_token,
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            }
        )

        redirect_url = app.get_webhook_url("redirect")
        logger.info(f"To continue, open this link in a new tab: {redirect_url}")

        for _ in range(60):
            time.sleep(5)
            state = auth_state.get_all(force_reload=True)
            if state.get("refresh_token"):
                logger.info("Successfully retrieved refresh token")
                break
            if state.get("error"):
                raise ActionFailure(
                    "OAuth authorization failed. Check the browser tab for details."
                )
        else:
            raise ActionFailure(
                "Timed out waiting for OAuth authorization. Please re-run test connectivity."
            )

        _url_get_token = (
            URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
        )
        _exchange_refresh_token(asset, _url_get_token)

    @app.test_connectivity()
    def test_connectivity(soar: SOARClient, asset: Asset) -> None:
        """Validate connection using the configured credentials"""
        if asset.use_client_credentials:
            _test_connectivity_client_credentials(asset)
        elif asset.username and asset.password:
            _test_connectivity_username_password(asset)
        else:
            _test_connectivity_oauth(asset)

        logger.info("Obtaining Salesforce API version")
        try:
            resp = httpx.get(
                _get_salesforce_instance_url(asset) + "/services/data/",
                headers={"Authorization": f"Bearer {_get_access_token(asset)}"},
                timeout=SALESFORCE_DEFAULT_TIMEOUT,
                verify=False,  # noqa: S501
            )
            resp.raise_for_status()
            versions = resp.json()
            latest = versions[-1]["url"]
            asset.cache_state["latest_version"] = latest
            logger.info(f"Latest Salesforce API version: {latest}")
        except Exception as e:
            raise ActionFailure(
                f"Connected but failed to fetch API version: {e}"
            ) from e

    return register_actions(app)


def _test_connectivity_username_password(asset: Asset) -> None:
    """Legacy username + password OAuth flow."""
    url_get_token = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN

    try:
        resp = httpx.post(
            url_get_token,
            data={
                "grant_type": "password",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "username": asset.username,
                "password": asset.password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token request failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(
            f"Salesforce rejected credentials: {resp_json.get('error_description') or resp_json['error']}"
        )

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]
    logger.info("Successfully obtained access token via username-password flow")


def _test_connectivity_client_credentials(asset: Asset) -> None:
    """Client credentials (server-to-server) OAuth flow."""
    from urllib.parse import urlparse

    domain_url = (asset.domain_url or "").strip()
    if not domain_url:
        raise ActionFailure(
            "My Domain URL must be set when using Client Credentials flow."
        )
    if "://" not in domain_url:
        domain_url = f"https://{domain_url}"
    parsed = urlparse(domain_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ActionFailure(
            "My Domain URL must be a full HTTPS URL, e.g. https://example.my.salesforce.com"
        )
    if not parsed.netloc.lower().endswith(".my.salesforce.com"):
        raise ActionFailure(
            "My Domain URL must end in .my.salesforce.com. Do not use login.salesforce.com or test.salesforce.com."
        )

    token_url = f"{parsed.scheme}://{parsed.netloc}/services/oauth2/token"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token request failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(
            f"Salesforce rejected client credentials: {resp_json.get('error_description') or resp_json['error']}"
        )

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]
    logger.info("Successfully obtained access token via client credentials flow")


def _exchange_refresh_token(asset: Asset, token_url: str) -> None:
    """Exchange the stored refresh token for a fresh access token and persist instance_url."""
    refresh_token = asset.auth_state.get("refresh_token")
    if not refresh_token:
        raise ActionFailure("No refresh token found. Re-run test connectivity.")

    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token refresh failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(
            f"Salesforce rejected token refresh: {resp_json.get('error_description') or resp_json['error']}"
        )

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]

    if new_refresh := resp_json.get("refresh_token"):
        asset.auth_state["refresh_token"] = new_refresh


def _get_access_token(asset: Asset) -> str:
    """Return the current access token from auth state."""
    token = asset.auth_state.get("access_token")
    if not token:
        raise ActionFailure("No access token found. Re-run test connectivity.")
    return token


def _get_salesforce_instance_url(asset: Asset) -> str:
    """Return the Salesforce instance URL from auth state."""
    url = asset.auth_state.get("instance_url")
    if not url:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    return url


app: App = create_salesforce_soar_connector_app()


if __name__ == "__main__":
    app.cli()
