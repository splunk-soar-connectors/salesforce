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

from src.actions.create_ticket import CreateTicketParams, create_ticket
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.app import GetTicketParams, get_ticket
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_get_ticket_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    subject = f"SDK get ticket live test {uuid4()}"
    created = create_ticket(
        CreateTicketParams(subject=subject, description="Get ticket live coverage"),
        app.soar_client,
        asset,
    )

    try:
        result = unwrap(get_ticket)(
            GetTicketParams(id=created.id),
            app.soar_client,
            asset,
        )

        assert result.Id == created.id
        assert result.Subject == subject
        assert result.attributes.type == "Case"
        assert result.attributes.url.endswith(f"/sobjects/Case/{created.id}")
        assert result.model_extra is not None
        assert app.soar_client.get_message() == "Successfully retrieved Case"
    finally:
        delete_ticket(
            DeleteTicketParams(id=created.id),
            app.soar_client,
            asset,
        )
