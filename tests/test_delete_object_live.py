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

import pytest
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure

from src.actions.create_object import CreateObjectParams, create_object
from src.actions.get_object import GetObjectParams, get_object
from src.app import DeleteObjectParams, delete_object
from src.asset import Asset
from src.auth import get_salesforce_client
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_delete_object_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)
    created = create_object(
        CreateObjectParams(
            sobject="Account",
            field_values=json.dumps({"Name": f"SDK live test {uuid4()}"}),
        ),
        app.soar_client,
        asset,
    )
    delete_object_handler = cast(
        Callable[[DeleteObjectParams, SOARClient, Asset], ActionOutput],
        delete_object.__wrapped__,  # type: ignore[attr-defined]
    )

    try:
        result = delete_object_handler(
            DeleteObjectParams(sobject="Account", id=created.id),
            app.soar_client,
            asset,
        )

        assert result.model_dump() == {}
        assert app.soar_client.get_message() == "Successfully deleted the Account"
        with pytest.raises(ActionFailure, match="Salesforce API error 404"):
            get_object(
                GetObjectParams(sobject="Account", id=created.id),
                app.soar_client,
                asset,
            )
    finally:
        latest_version = asset.cache_state["latest_version"]
        with get_salesforce_client(asset) as client:
            cleanup_response = client.delete(
                f"{latest_version.rstrip('/')}/sobjects/Account/{created.id}/"
            )
            if cleanup_response.status_code != 404:
                cleanup_response.raise_for_status()

    with pytest.raises(ActionFailure, match="Invalid value for 'sobject'"):
        delete_object_handler(
            DeleteObjectParams(sobject="../Account", id=created.id),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match="Invalid value for 'id'"):
        delete_object_handler(
            DeleteObjectParams(sobject="Account", id="../record"),
            app.soar_client,
            asset,
        )
