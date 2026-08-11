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
from src.actions.delete_object import DeleteObjectParams, delete_object
from src.actions.delete_ticket import DeleteTicketParams, delete_ticket
from src.app import PostChatterParams, post_chatter
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_post_chatter_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_ticket(
        CreateTicketParams(subject=f"SDK post chatter live test {uuid4()}"),
        app.soar_client,
        asset,
    )
    chatter_id: str | None = None

    try:
        result = unwrap(post_chatter)(
            PostChatterParams(
                id=created.id,
                title="SDK live test",
                body=f"Posted by SDK live coverage {uuid4()}",
            ),
            app.soar_client,
            asset,
        )

        chatter_id = result.id
        assert result.success is True
        summary = app.soar_client.get_summary()
        assert summary is not None
        assert summary.model_dump() == {"obj_id": chatter_id}
        assert app.soar_client.get_message() == "Successfully posted to chatter"
    finally:
        if chatter_id is not None:
            delete_object(
                DeleteObjectParams(sobject="FeedItem", id=chatter_id),
                app.soar_client,
                asset,
            )
        delete_ticket(
            DeleteTicketParams(id=created.id),
            app.soar_client,
            asset,
        )
