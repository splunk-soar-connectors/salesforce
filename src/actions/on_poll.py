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
from urllib.parse import quote

from soar_sdk.abstract import SOARClient
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams

from ..asset import Asset
from ..auth import get_salesforce_client
from ..state import (
    CONTAINER_SDI_SALT_STATE_KEY,
    POLL_OFFSET_STATE_KEY,
    get_latest_api_version,
    migrate_legacy_ingest_state,
    persist_poll_offset,
)
from .utils import request_salesforce_json


MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)
INVALID_LIST_RESPONSE_ERROR = (
    "Salesforce returned an unexpected polling list-view response"
)
INVALID_BATCH_RESPONSE_ERROR = (
    "Salesforce returned an unexpected polling batch response"
)
MAX_OBJECTS_PER_PAGE = 2000
MAX_PAGES_PER_POLL = 100
BATCH_SIZE = 25
OFFSET_LIMIT_ERROR_MARKERS = (
    "Maximum SOQL offset allowed is",
    "pageToken parameter must be between",
)

SEVERITY_MAP = {
    "severity 1 (high impact)": "high",
    "severity 2 (medium impact": "medium",
    "severity 3 (low impact)": "low",
    "severity 4 (false positive)": "low",
}
SENSITIVITY_MAP = {
    "sensitive": "red",
    "not sensitive": "white",
}


def _validate_integer(value: float | int, key: str, *, allow_zero: bool = False) -> int:
    try:
        if not float(value).is_integer():
            raise ValueError
        integer = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ActionFailure(
            f"Please provide a valid integer value in the '{key}' parameter"
        ) from error

    if integer < 0:
        raise ActionFailure(
            f"Please provide a valid non-negative integer value in the '{key}' parameter"
        )
    if not allow_zero and integer == 0:
        raise ActionFailure(f'Please provide non-zero positive integer in "{key}"')
    return integer


def _strip_format_controls(value: object) -> object:
    if not isinstance(value, str):
        return value
    return "".join(
        character for character in value if unicodedata.category(character) != "Cf"
    )


def _extract_record_id(record: object) -> str | None:
    if not isinstance(record, dict):
        return None

    fields = record.get("fields")
    if isinstance(fields, dict):
        id_field = fields.get("Id")
        if isinstance(id_field, dict) and isinstance(id_field.get("value"), str):
            return id_field["value"]

    columns = record.get("columns")
    if isinstance(columns, list):
        for column in columns:
            if (
                isinstance(column, dict)
                and column.get("fieldNameOrPath") == "Id"
                and isinstance(column.get("value"), str)
            ):
                return column["value"]
    return None


def _parse_cef_name_map(asset: Asset) -> dict[str, str]:
    if not asset.cef_name_map:
        return {}
    try:
        mapping = json.loads(asset.cef_name_map)
    except (TypeError, ValueError) as error:
        raise ActionFailure(f"Error parsing cef_name_map {error}") from error
    if not isinstance(mapping, dict):
        raise ActionFailure("cef_name_map must be a JSON object")
    for key, value in mapping.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ActionFailure(
                "cef_name_map must contain non-empty string keys and values"
            )
        if not key.strip() or not value.strip():
            raise ActionFailure(
                "cef_name_map must contain non-empty string keys and values"
            )
    return mapping


def _poll_list_view(
    asset: Asset,
    endpoint: str,
    *,
    offset: int,
    max_records: int | None,
) -> tuple[int, list[object]]:
    records: list[object] = []
    with get_salesforce_client(asset) as client:
        for _page_number in range(MAX_PAGES_PER_POLL):
            try:
                page = request_salesforce_json(
                    client,
                    "GET",
                    endpoint,
                    params={
                        "sortBy": "LastModifiedDate",
                        "pageSize": str(MAX_OBJECTS_PER_PAGE),
                        "pageToken": str(offset),
                    },
                    invalid_response_error=INVALID_LIST_RESPONSE_ERROR,
                )
            except ActionFailure as error:
                error_message = str(error)
                if any(
                    marker in error_message for marker in OFFSET_LIMIT_ERROR_MARKERS
                ):
                    if records:
                        return offset, records
                    raise ActionFailure(
                        f"Polling offset {offset} exceeds the Salesforce limit; "
                        "reset the asset polling state to resume ingestion"
                    ) from error
                if "The requested resource does not exist" in error_message:
                    raise ActionFailure(
                        "No listview with that specified name was found"
                    ) from error
                raise

            page_records = page.get("records")
            if not isinstance(page_records, list):
                raise ActionFailure(INVALID_LIST_RESPONSE_ERROR)
            records.extend(page_records)

            if max_records is not None and len(records) >= max_records:
                selected = records[:max_records]
                return offset + len(selected), selected
            offset += len(page_records)
            if len(page_records) < MAX_OBJECTS_PER_PAGE:
                return offset, records

    return offset, records


def _batch_get_records(
    asset: Asset,
    endpoint: str,
    *,
    latest_version: str,
    sobject: str,
    indexed_ids: list[tuple[int, str]],
) -> tuple[list[tuple[int, dict[str, object]]], list[int]]:
    records: list[tuple[int, dict[str, object]]] = []
    failed_indices: list[int] = []

    with get_salesforce_client(asset) as client:
        for batch_start in range(0, len(indexed_ids), BATCH_SIZE):
            batch = indexed_ids[batch_start : batch_start + BATCH_SIZE]
            response = request_salesforce_json(
                client,
                "POST",
                endpoint,
                json={
                    "batchRequests": [
                        {
                            "method": "GET",
                            "url": (
                                f"{latest_version.rstrip('/')}/sobjects/"
                                f"{quote(sobject, safe='')}/{quote(record_id, safe='')}/"
                            ),
                        }
                        for _record_index, record_id in batch
                    ]
                },
                invalid_response_error=INVALID_BATCH_RESPONSE_ERROR,
            )
            results = response.get("results")
            if not isinstance(results, list) or len(results) != len(batch):
                raise ActionFailure(INVALID_BATCH_RESPONSE_ERROR)

            for (record_index, _record_id), result in zip(batch, results, strict=True):
                if not isinstance(result, dict):
                    raise ActionFailure(INVALID_BATCH_RESPONSE_ERROR)
                record = result.get("result")
                if result.get("statusCode") != 200 or not isinstance(record, dict):
                    failed_indices.append(record_index)
                    continue
                records.append((record_index, record))

    return records, failed_indices


def _record_to_items(
    asset: Asset,
    record: dict[str, object],
    *,
    sobject: str,
    cef_name_map: dict[str, str],
    include_view_date: bool,
) -> tuple[Container, Artifact]:
    cef: dict[str, object] = {}
    cef_types: dict[str, list[str]] = {}
    for key, value in record.items():
        if key == "attributes":
            continue
        cef_key = cef_name_map.get(key, key)
        cef[cef_key] = _strip_format_controls(value)
        if key.endswith("Id") and value is not None:
            cef_types[cef_key] = ["salesforce object id"]

    if not include_view_date:
        cef.pop("LastViewedDate", None)
        cef.pop("LastReferencedDate", None)

    container_name = cef.get("Subject")
    if not isinstance(container_name, str) or not container_name:
        number = record.get("CaseNumber") or record.get("Id", "")
        container_name = f"Salesforce {sobject} Object # {number}"

    record_id = record.get("Id")
    if not isinstance(record_id, str):
        raise ActionFailure(INVALID_BATCH_RESPONSE_ERROR)
    salt = asset.ingest_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    if not isinstance(salt, str) or not salt:
        salt = secrets.token_urlsafe(32)
        asset.ingest_state[CONTAINER_SDI_SALT_STATE_KEY] = salt

    container_sdi = hashlib.sha256(f"{salt}:{sobject}:{record_id}".encode()).hexdigest()
    artifact_sdi = hashlib.sha256(
        json.dumps(
            {"name": sobject, "cef": cef, "cef_types": cef_types},
            sort_keys=True,
        ).encode()
    ).hexdigest()

    severity_value = record.get("Incident_Severity__c")
    severity = None
    if isinstance(severity_value, str) and severity_value:
        severity = SEVERITY_MAP.get(severity_value.lower(), "medium")
    sensitivity_value = record.get("Incident_Sensitivity__c")
    sensitivity = None
    if isinstance(sensitivity_value, str) and sensitivity_value:
        sensitivity = SENSITIVITY_MAP.get(sensitivity_value.lower(), "amber")

    return (
        Container(
            name=container_name,
            source_data_identifier=container_sdi,
            severity=severity,
            sensitivity=sensitivity,
        ),
        Artifact(
            name=sobject,
            source_data_identifier=artifact_sdi,
            cef=cef,
            cef_types=cef_types or None,
        ),
    )


def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Container | Artifact]:
    del soar
    migrate_legacy_ingest_state(asset)
    sobject = asset.poll_sobject or "Case"
    view_name = asset.poll_view_name
    if not view_name:
        raise ActionFailure("Error: Must specify poll_view_name")

    latest_version = get_latest_api_version(asset)
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    cef_name_map = _parse_cef_name_map(asset)
    include_view_date = bool(asset.last_view_date)
    is_manual = params.is_manual_poll()
    if is_manual:
        offset = 0
        max_records = _validate_integer(
            params.container_count if params.container_count is not None else 10,
            "container_count",
        )
    else:
        offset = _validate_integer(
            asset.ingest_state.get(POLL_OFFSET_STATE_KEY, 0),
            POLL_OFFSET_STATE_KEY,
            allow_zero=True,
        )
        max_records = None
        if offset == 0:
            max_records = _validate_integer(
                asset.first_ingestion_max
                if asset.first_ingestion_max is not None
                else 10,
                "first_ingestion_max",
            )

    list_endpoint = (
        f"{latest_version.rstrip('/')}/ui-api/list-records/"
        f"{quote(sobject, safe='')}/{quote(view_name, safe='')}"
    )
    new_offset, list_records = _poll_list_view(
        asset,
        list_endpoint,
        offset=offset,
        max_records=max_records,
    )

    indexed_ids: list[tuple[int, str]] = []
    missing_indices: list[int] = []
    for record_index, record in enumerate(list_records):
        record_id = _extract_record_id(record)
        if record_id is None:
            missing_indices.append(record_index)
        else:
            indexed_ids.append((record_index, record_id))

    batch_endpoint = f"{latest_version.rstrip('/')}/composite/batch/"
    records, failed_indices = _batch_get_records(
        asset,
        batch_endpoint,
        latest_version=latest_version,
        sobject=sobject,
        indexed_ids=indexed_ids,
    )
    failed_indices.extend(missing_indices)

    for _record_index, record in records:
        container, artifact = _record_to_items(
            asset,
            record,
            sobject=sobject,
            cef_name_map=cef_name_map,
            include_view_date=include_view_date,
        )
        yield container
        yield artifact

    if not is_manual:
        if failed_indices:
            persist_poll_offset(asset, offset + min(failed_indices))
        else:
            asset.ingest_state[POLL_OFFSET_STATE_KEY] = new_offset

    if failed_indices:
        raise ActionFailure(
            f"{len(failed_indices)} record(s) failed to ingest; "
            "the failed records will be retried"
        )
