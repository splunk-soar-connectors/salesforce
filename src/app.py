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
import secrets
import unicodedata
from collections.abc import Iterator

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams

from .actions import register_actions
from .asset import Asset
from .salesforce_client import SalesforceClient
from .test_connectivity import run_test_connectivity
from .webhooks import register_webhooks

logger = getLogger()

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


def _strip_format_controls(value):
    if not isinstance(value, str):
        return value
    return "".join(c for c in value if unicodedata.category(c) != "Cf")


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
    )
    register_webhooks(app)

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

        # Prepend any IDs that failed in the previous scheduled poll so they are retried first.
        pending_retry: list[str] = (
            [] if is_manual else list(asset.ingest_state.get("failed_record_ids") or [])
        )

        if not list_records and not pending_retry:
            logger.info("No new records found.")
            if not is_manual:
                asset.ingest_state["cur_offset"] = new_offset
            return
        record_ids = pending_retry + [
            _id for row in list_records if (_id := _extract_id_from_record(row))
        ]

        logger.info(
            f"Extracted {len(record_ids)} record IDs from list-view rows ({len(pending_retry)} retried from previous poll)"
        )

        full_records: list[dict] = []
        all_failed_ids: list[str] = []
        for i in range(0, len(record_ids), 25):
            batch_records, failed_ids = client.batch_get(
                sobject, record_ids[i : i + 25]
            )
            full_records.extend(batch_records)
            all_failed_ids.extend(failed_ids)

        logger.info(
            f"Fetched {len(full_records)} full {sobject} records; "
            f"{len(all_failed_ids)} failed and will be retried next poll"
        )

        for record in full_records:
            cef: dict = {}
            cef_types: dict = {}

            for k, v in record.items():
                if k == "attributes":
                    continue
                cef_key = cef_name_map.get(k, k)
                cef[cef_key] = _strip_format_controls(v)
                if k.endswith("Id") and v is not None:
                    cef_types[cef_key] = ["salesforce object id"]

            if not include_view_date:
                cef.pop("LastViewedDate", None)
                cef.pop("LastReferencedDate", None)

            container_name = (
                cef.get("Subject")
                or f"Salesforce {sobject} # {record.get('CaseNumber') or record.get('Id', '')}"
            )

            record_id = record.get("Id", "")
            salt = asset.ingest_state.get("container_sdi_salt")
            if not isinstance(salt, str) or not salt:
                salt = secrets.token_urlsafe(32)
                asset.ingest_state["container_sdi_salt"] = salt
            container_sdi = hashlib.sha256(
                f"{salt}:{sobject}:{record_id}".encode()
            ).hexdigest()
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
            asset.ingest_state["failed_record_ids"] = all_failed_ids
            logger.info(
                f"Saved poll offset: {new_offset}; "
                f"{len(all_failed_ids)} record(s) queued for retry"
            )

    @app.test_connectivity()
    def test_connectivity(soar: SOARClient, asset: Asset) -> None:
        """Validate connection using the configured credentials"""
        run_test_connectivity(
            asset,
            oauth_callback_url=app.get_webhook_url("start_oauth"),
        )

    return register_actions(app)


app: App = create_salesforce_soar_connector_app()


if __name__ == "__main__":
    app.cli()
