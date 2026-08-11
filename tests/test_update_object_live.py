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

from src.actions.create_object import CreateObjectParams, create_object
from src.actions.delete_object import DeleteObjectParams, delete_object
from src.actions.get_object import GetObjectParams, get_object
from src.actions.update_object import UpdateObjectParams, update_object
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_update_object_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    original_name = f"SDK update object live test {uuid4()}"
    updated_name = f"{original_name} updated"
    created = create_object(
        CreateObjectParams(
            sobject="Account",
            field_values=json.dumps({"Name": original_name}),
        ),
        app.soar_client,
        asset,
    )

    try:
        result = unwrap(update_object)(
            UpdateObjectParams(
                sobject="Account",
                id=created.id,
                field_values=json.dumps({"Name": updated_name}),
            ),
            app.soar_client,
            asset,
        )

        assert result.model_dump() == {}
        summary = app.soar_client.get_summary()
        assert summary is not None
        assert summary.model_dump() == {"obj_id": created.id}
        assert app.soar_client.get_message() == "Successfully updated the Account"

        account = get_object(
            GetObjectParams(sobject="Account", id=created.id),
            app.soar_client,
            asset,
        )
        assert account.model_extra is not None
        assert account.model_extra["Name"] == updated_name
    finally:
        delete_object(
            DeleteObjectParams(sobject="Account", id=created.id),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match="Error reading 'field_values'"):
        unwrap(update_object)(
            UpdateObjectParams(
                sobject="Account",
                id=created.id,
                field_values="not JSON",
            ),
            app.soar_client,
            asset,
        )
