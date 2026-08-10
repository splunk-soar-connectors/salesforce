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
from soar_sdk.app import App
from soar_sdk.asset_state import AssetState

from src.app import create_salesforce_connector_app
from src.asset import Asset

from .config import RedactedTestConfig, load_test_config


APP_ID = "6c1316b0-88a7-4864-b684-3170f6c455be"


class LiveTestAsset(Asset):
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"


@pytest.fixture(scope="session")
def test_config() -> RedactedTestConfig:
    return load_test_config()


@pytest.fixture
def app() -> App:
    return create_salesforce_connector_app()


@pytest.fixture
def asset(test_config: RedactedTestConfig, app: App) -> Asset:
    asset_id = test_config.get("SOAR_ASSET_ID", "123")
    salesforce_asset = LiveTestAsset.model_validate(
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
        encrypted=True,
    )
    salesforce_asset._cache_state = AssetState(
        app.actions_manager,
        "cache",
        asset_id,
        app_id=APP_ID,
        encrypted=True,
    )
    return salesforce_asset
