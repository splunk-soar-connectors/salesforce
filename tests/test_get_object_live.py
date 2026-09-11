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
import httpx
import pytest
from soar_sdk.app import App
from soar_sdk.auth import StaticTokenAuth
from soar_sdk.exceptions import ActionFailure

from src.actions.get_object import GetObjectParams, get_object
from src.asset import Asset
from src.auth import get_access_token, get_instance_origin
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_get_object_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)

    token = get_access_token(asset)
    instance_origin = get_instance_origin(asset, token)
    latest_version = asset.cache_state["latest_version"]
    with httpx.Client(
        base_url=instance_origin,
        auth=StaticTokenAuth(token),
        timeout=30.0,
    ) as client:
        response = client.get(
            f"{latest_version.rstrip('/')}/query/",
            params={"q": "SELECT Id FROM User LIMIT 1"},
        )
        response.raise_for_status()
        record_id = response.json()["records"][0]["Id"]

    result = get_object(
        GetObjectParams(sobject="User", id=record_id),
        app.soar_client,
        asset,
    )

    assert result.Id == record_id
    assert result.model_extra is not None
    assert "attributes" in result.model_extra
    assert app.soar_client.get_message() == "Successfully retrieved User"

    with pytest.raises(ActionFailure, match="Salesforce API error 404"):
        get_object(
            GetObjectParams(sobject="Case", id=record_id),
            app.soar_client,
            asset,
        )
