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
from inspect import unwrap
from uuid import uuid4

import pytest
from soar_sdk.app import App
from soar_sdk.models.artifact import Artifact
from soar_sdk.models.container import Container
from soar_sdk.params import OnPollParams

from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.actions.get_object import GetObjectParams, get_object
from src.actions.on_poll import on_poll
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


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
                app.soar_client,
                asset,
                OnPollParams(container_count=1),
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
                app.soar_client,
                asset,
                OnPollParams(),
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
