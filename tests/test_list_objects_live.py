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
from src.app import ListObjectsParams, list_objects
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_list_objects_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_object(
        CreateObjectParams(
            sobject="Account",
            field_values=json.dumps(
                {"Name": f"SDK list objects live test {uuid4()}"}
            ),
        ),
        app.soar_client,
        asset,
    )

    try:
        get_object(
            GetObjectParams(sobject="Account", id=created.id),
            app.soar_client,
            asset,
        )

        discovery_result = unwrap(list_objects)(
            ListObjectsParams(sobject="Account"),
            app.soar_client,
            asset,
        )
        assert discovery_result == []
        discovery_summary = app.soar_client.get_summary()
        assert discovery_summary is not None
        view_names = discovery_summary.model_dump()["view_names"]
        assert "RecentlyViewedAccounts" in view_names
        assert app.soar_client.get_message() == "Listed the valid view names"

        result = unwrap(list_objects)(
            ListObjectsParams(
                sobject="Account",
                view_name="RecentlyViewedAccounts",
                limit=1,
                offset=0,
            ),
            app.soar_client,
            asset,
        )
        assert len(result) == 1
        assert result[0].columns.Id.value
        assert result[0].columns.model_extra is not None
        summary = app.soar_client.get_summary()
        assert summary is not None
        assert summary.model_dump() == {"num_objects": 1}
        assert app.soar_client.get_message() == (
            "Successfully fetched a list of Account objects"
        )
    finally:
        delete_object(
            DeleteObjectParams(sobject="Account", id=created.id),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match="Specified list view name was not found"):
        unwrap(list_objects)(
            ListObjectsParams(sobject="Account", view_name="NotARealView"),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match='non-zero positive integer in "limit"'):
        unwrap(list_objects)(
            ListObjectsParams(
                sobject="Account",
                view_name="RecentlyViewedAccounts",
                limit=0,
            ),
            app.soar_client,
            asset,
        )
