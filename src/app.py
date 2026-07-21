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
import hashlib
import json
from collections.abc import Iterator

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
from .auth import (
    authenticate_client_credentials,
    authenticate_username_password,
    get_access_token,
    get_instance_url,
    handle_oauth_callback,
    start_oauth_flow,
    wait_for_oauth_and_finalize,
)
from .salesforce_client import SalesforceClient

logger = getLogger()

SALESFORCE_DEFAULT_TIMEOUT = 30

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

    @app.webhook("/start_oauth", allowed_methods=["GET"])
    def handle_start_oauth(request: WebhookRequest) -> WebhookResponse:
        """Receives the Salesforce OAuth callback and stores the authorization code."""
        return handle_oauth_callback(request.asset, request.query)

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
        """Browser-based OAuth with PKCE flow via the SDK AuthorizationCodeFlow."""
        redirect_uri = app.get_webhook_url("start_oauth")
        auth_url = start_oauth_flow(asset, redirect_uri)
        logger.info(f"To continue, open this link in a new tab: {auth_url}")
        wait_for_oauth_and_finalize(asset, redirect_uri)

    @app.test_connectivity()
    def test_connectivity(soar: SOARClient, asset: Asset) -> None:
        """Validate connection using the configured credentials"""
        if asset.use_client_credentials:
            authenticate_client_credentials(asset)
        elif asset.username and asset.password:
            authenticate_username_password(asset)
        else:
            _test_connectivity_oauth(asset)

        logger.info("Obtaining Salesforce API version")
        try:
            resp = httpx.get(
                get_instance_url(asset) + "/services/data/",
                headers={"Authorization": f"Bearer {get_access_token(asset)}"},
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


app: App = create_salesforce_soar_connector_app()


if __name__ == "__main__":
    app.cli()
