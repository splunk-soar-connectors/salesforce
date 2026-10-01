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
from inspect import unwrap
from uuid import uuid4

import pytest
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams

from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.actions.get_object import GetObjectParams, get_object
from src.actions.on_poll import (
    _batch_get_records,
    _get_first_ingestion_limit,
    _record_to_items,
    on_poll,
)
from src.asset import Asset
from src.state import POLL_OFFSET_STATE_KEY, persist_poll_offset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_artifact_identifier_preserves_legacy_serialization(asset: Asset) -> None:
    record = {
        "attributes": {"type": "Case"},
        "Subject": "Legacy artifact identifier",
        "Id": "500000000000001",
    }
    legacy_artifact = {
        "cef": {
            "Subject": "Legacy artifact identifier",
            "Id": "500000000000001",
        },
        "cef_types": {"Id": ["salesforce object id"]},
        "name": "Case",
    }
    expected_identifier = hashlib.sha256(
        json.dumps(legacy_artifact).encode()
    ).hexdigest()

    _, artifact = _record_to_items(
        asset,
        record,
        sobject="Case",
        cef_name_map={},
        include_view_date=True,
    )

    assert artifact.source_data_identifier == expected_identifier


@pytest.mark.live
def test_on_poll_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_ticket(
        CreateTicketParams(subject=f"SDK on poll live test {uuid4()}"),
        app.soar_client,
        asset,
    )

    asset.poll_sobject = "Case"
    asset.poll_view_name = "RecentlyViewedCases"
    asset.first_ingestion_max = 1
    asset.last_view_date = False
    asset.cef_name_map = json.dumps({"Subject": "eventName"})
    asset.ingest_state["cur_offset"] = 0

    try:
        get_object(
            GetObjectParams(sobject="Case", id=created.id),
            app.soar_client,
            asset,
        )

        items = list(
            unwrap(on_poll)(
                OnPollParams(container_count=1),
                app.soar_client,
                asset,
            )
        )

        assert len(items) == 2
        container, artifact = items
        assert isinstance(container, Container)
        assert isinstance(artifact, Artifact)
        assert container.source_data_identifier is not None
        assert len(container.source_data_identifier) == 64
        assert artifact.name == "Case"
        assert artifact.source_data_identifier is not None
        assert len(artifact.source_data_identifier) == 64
        assert artifact.cef is not None
        assert artifact.cef["Id"]
        assert artifact.cef["eventName"]
        assert "LastViewedDate" not in artifact.cef
        assert "LastReferencedDate" not in artifact.cef
        assert artifact.cef_types is not None
        assert artifact.cef_types["Id"] == ["salesforce object id"]
        assert asset.ingest_state["cur_offset"] == 0

        scheduled_items = list(
            unwrap(on_poll)(
                OnPollParams(),
                app.soar_client,
                asset,
            )
        )
        assert len(scheduled_items) == 2
        assert asset.ingest_state["cur_offset"] == 1
    finally:
        delete_ticket(
            DeleteTicketParams(id=created.id),
            app.soar_client,
            asset,
        )


@pytest.mark.live
def test_failed_record_offset_survives_poll_rollback_live(asset: Asset) -> None:
    backend = asset.ingest_state.backend
    original_state = backend.load_state() or {}

    try:
        asset.ingest_state.put_all({POLL_OFFSET_STATE_KEY: 100})
        asset.ingest_state.begin_transaction()

        persist_poll_offset(asset, 107)
        asset.ingest_state.rollback()

        assert asset.ingest_state[POLL_OFFSET_STATE_KEY] == 107
    finally:
        if asset.ingest_state.in_transaction:
            asset.ingest_state.rollback()
        backend.save_state(original_state)


@pytest.mark.live
def test_poll_offset_limit_includes_recovery_guidance_live(
    app: App, asset: Asset
) -> None:
    backend = asset.ingest_state.backend
    original_state = backend.load_state() or {}
    offset = 10_000_000

    try:
        run_test_connectivity(asset)
        asset.poll_sobject = "Case"
        asset.poll_view_name = "RecentlyViewedCases"
        asset.ingest_state[POLL_OFFSET_STATE_KEY] = offset

        with pytest.raises(ActionFailure) as exc_info:
            list(unwrap(on_poll)(OnPollParams(), app.soar_client, asset))

        assert exc_info.value.message == (
            f"Polling offset {offset} exceeds the Salesforce limit; "
            "reset the asset polling state to resume ingestion"
        )
    finally:
        backend.save_state(original_state)


@pytest.mark.live
def test_empty_poll_skips_batch_authentication_live(asset: Asset) -> None:
    original_use_client_credentials = asset.use_client_credentials
    original_domain_url = asset.domain_url

    try:
        asset.use_client_credentials = True
        asset.domain_url = None

        assert _batch_get_records(
            asset,
            "/services/data/v65.0/composite/batch/",
            latest_version="/services/data/v65.0",
            sobject="Case",
            indexed_ids=[],
        ) == ([], [])
    finally:
        asset.use_client_credentials = original_use_client_credentials
        asset.domain_url = original_domain_url


@pytest.mark.live
def test_explicit_null_first_ingestion_max_is_unlimited_live(asset: Asset) -> None:
    original_first_ingestion_max = asset.first_ingestion_max

    try:
        asset.first_ingestion_max = None
        assert _get_first_ingestion_limit(asset) is None

        asset.first_ingestion_max = 10
        assert _get_first_ingestion_limit(asset) == 10
    finally:
        asset.first_ingestion_max = original_first_ingestion_max
