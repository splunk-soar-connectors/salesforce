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
import pytest
from soar_sdk.asset_state import AssetState

from src.app import create_salesforce_connector_app
from src.asset import Asset

from .config import load_test_config


APP_ID = "6c1316b0-88a7-4864-b684-3170f6c455be"


@pytest.fixture(scope="session")
def test_config() -> dict[str, str]:
    return load_test_config()


@pytest.fixture
def asset(test_config: dict[str, str]) -> Asset:
    app = create_salesforce_connector_app()
    asset_id = test_config.get("SOAR_ASSET_ID", "123")
    salesforce_asset = Asset.model_validate(
        {
            "client_id": test_config["client_id"],
            "client_secret": test_config["client_secret"],
            "domain_url": test_config["domain_url"],
            "use_client_credentials": True,
        }
    )
    salesforce_asset._auth_state = AssetState(
        app.actions_manager,
        "auth",
        asset_id,
        app_id=APP_ID,
        encrypted=False,
    )
    return salesforce_asset
