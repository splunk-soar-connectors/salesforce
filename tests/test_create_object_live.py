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
from uuid import uuid4

import httpx
import pytest
from soar_sdk.app import App
from soar_sdk.auth import StaticTokenAuth
from soar_sdk.exceptions import ActionFailure

from src.actions.create_object import (
    CreateObjectParams,
    CreateObjectSummary,
    create_object,
)
from src.asset import Asset
from src.auth import get_access_token, get_instance_origin
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_create_object_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)

    result = create_object(
        CreateObjectParams(
            sobject="Account",
            field_values=json.dumps({"Name": f"SDK live test {uuid4()}"}),
        ),
        app.soar_client,
        asset,
    )

    try:
        assert result.success is True
        assert isinstance(result.id, str)
        assert app.soar_client.get_summary() == CreateObjectSummary(obj_id=result.id)
        assert app.soar_client.get_message() == "Successfully created a new Account"
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
                f"{latest_version.rstrip('/')}/sobjects/Account/{result.id}/"
            )
            response.raise_for_status()

    with pytest.raises(ActionFailure, match="Error reading 'field_values'"):
        create_object(
            CreateObjectParams(sobject="Account", field_values="not JSON"),
            app.soar_client,
            asset,
        )
