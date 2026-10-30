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
from inspect import unwrap
from uuid import uuid4

import pytest
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure

from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.actions.get_object import GetObjectParams, get_object
from src.asset import Asset
from src.auth import get_salesforce_client
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_delete_ticket_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_ticket(
        CreateTicketParams(
            subject=f"SDK delete ticket live test {uuid4()}",
            description="Created for delete ticket live coverage",
        ),
        app.soar_client,
        asset,
    )

    try:
        result = unwrap(delete_ticket)(
            DeleteTicketParams(id=created.id),
            app.soar_client,
            asset,
        )

        assert result.model_dump() == {}
        assert app.soar_client.get_message() == "Successfully deleted the Case"
        with pytest.raises(ActionFailure, match="Salesforce API error 404"):
            get_object(
                GetObjectParams(sobject="Case", id=created.id),
                app.soar_client,
                asset,
            )
    finally:
        latest_version = asset.cache_state["latest_version"]
        with get_salesforce_client(asset) as client:
            cleanup_response = client.delete(
                f"{latest_version.rstrip('/')}/sobjects/Case/{created.id}/"
            )
            if cleanup_response.status_code != 404:
                cleanup_response.raise_for_status()

    with pytest.raises(ActionFailure, match="Invalid value for 'id'"):
        unwrap(delete_ticket)(
            DeleteTicketParams(id="../record"),
            app.soar_client,
            asset,
        )
