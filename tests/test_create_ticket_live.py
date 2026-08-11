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
from collections.abc import Callable
from typing import cast
from uuid import uuid4

import httpx
import pytest
from soar_sdk.app import App
from soar_sdk.abstract import SOARClient
from soar_sdk.auth import StaticTokenAuth
from soar_sdk.exceptions import ActionFailure

from src.actions.get_object import GetObjectParams, get_object
from src.app import CreateTicketOutput, CreateTicketParams, create_ticket
from src.asset import Asset
from src.auth import get_access_token, get_instance_origin
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_create_ticket_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    subject = f"SDK live test {uuid4()}"
    create_ticket_handler = cast(
        Callable[[CreateTicketParams, SOARClient, Asset], CreateTicketOutput],
        create_ticket.__wrapped__,  # type: ignore[attr-defined]
    )

    result = create_ticket_handler(
        CreateTicketParams(
            subject=subject,
            priority="High",
            description="Created by the Salesforce SDK live test",
            field_values=json.dumps(
                {
                    "Subject": "This value must be overridden",
                    "Origin": "Web",
                }
            ),
        ),
        app.soar_client,
        asset,
    )

    try:
        assert result.success is True
        assert isinstance(result.id, str)
        summary = app.soar_client.get_summary()
        assert summary is not None
        assert summary.model_dump() == {"obj_id": result.id}
        assert app.soar_client.get_message() == "Successfully created a new Case"

        ticket = get_object(
            GetObjectParams(sobject="Case", id=result.id),
            app.soar_client,
            asset,
        )
        assert ticket.model_extra is not None
        assert ticket.model_extra["Subject"] == subject
        assert ticket.model_extra["Priority"] == "High"
        assert ticket.model_extra["Description"] == (
            "Created by the Salesforce SDK live test"
        )
        assert ticket.model_extra["Origin"] == "Web"
    finally:
        token = get_access_token(asset)
        instance_origin = get_instance_origin(asset, token)
        latest_version = asset.cache_state["latest_version"]
        with httpx.Client(
            base_url=instance_origin,
            auth=StaticTokenAuth(token),
            timeout=30.0,
        ) as client:
            response = client.delete(
                f"{latest_version.rstrip('/')}/sobjects/Case/{result.id}/"
            )
            response.raise_for_status()

    with pytest.raises(ActionFailure, match="Error reading 'field_values'"):
        create_ticket_handler(
            CreateTicketParams(field_values="not JSON"),
            app.soar_client,
            asset,
        )
