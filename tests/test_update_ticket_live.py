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
from soar_sdk.exceptions import ActionFailure

from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.actions.get_object import GetObjectParams, get_object
from src.app import UpdateTicketParams, update_ticket
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_update_ticket_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_ticket(
        CreateTicketParams(
            subject=f"SDK update ticket live test {uuid4()}",
            description="Original description",
        ),
        app.soar_client,
        asset,
    )

    try:
        updated_subject = f"Updated by SDK {uuid4()}"
        result = unwrap(update_ticket)(
            UpdateTicketParams(
                id=created.id,
                subject=updated_subject,
                priority="High",
                description="Named description wins",
                field_values=json.dumps(
                    {
                        "Description": "Must be overridden",
                        "Origin": "Web",
                    }
                ),
            ),
            app.soar_client,
            asset,
        )

        assert result.model_dump() == {}
        summary = app.soar_client.get_summary()
        assert summary is not None
        assert summary.model_dump() == {"obj_id": created.id}
        assert app.soar_client.get_message() == "Successfully updated the Case"

        ticket = get_object(
            GetObjectParams(sobject="Case", id=created.id),
            app.soar_client,
            asset,
        )
        assert ticket.model_extra is not None
        assert ticket.model_extra["Subject"] == updated_subject
        assert ticket.model_extra["Priority"] == "High"
        assert ticket.model_extra["Description"] == "Named description wins"
        assert ticket.model_extra["Origin"] == "Web"
    finally:
        delete_ticket(
            DeleteTicketParams(id=created.id),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match="Error reading 'field_values'"):
        unwrap(update_ticket)(
            UpdateTicketParams(id=created.id, field_values="not JSON"),
            app.soar_client,
            asset,
        )

    with pytest.raises(
        ActionFailure,
        match="Please provide at least one optional parameter",
    ):
        unwrap(update_ticket)(
            UpdateTicketParams(id=created.id),
            app.soar_client,
            asset,
        )
