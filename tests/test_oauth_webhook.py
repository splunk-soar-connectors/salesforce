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
from soar_sdk.asset_state import AssetState
from soar_sdk.auth.models import OAuthSession, OAuthState
from soar_sdk.webhooks.models import WebhookRequest

from src.app import create_salesforce_connector_app
from src.asset import Asset
from src.webhooks.oauth import AUTHORIZATION_ERROR_STATE_KEY, oauth_callback


APP_ID = "6c1316b0-88a7-4864-b684-3170f6c455be"


def _asset_with_pending_oauth_session(state: str) -> Asset:
    app = create_salesforce_connector_app()
    asset = Asset(client_id="client-id", client_secret="client-secret")
    asset._auth_state = AssetState(
        app.actions_manager,
        "auth",
        "123",
        app_id=APP_ID,
        encrypted=True,
    )
    oauth_state = OAuthState(
        session=OAuthSession(
            session_id="session-id",
            asset_id="123",
            state=state,
        )
    )
    asset.auth_state.put_all(
        {"oauth": oauth_state.model_dump(mode="json", exclude_none=True)}
    )
    return asset


def _error_callback_request(asset: Asset, state: str) -> WebhookRequest[Asset]:
    return WebhookRequest[Asset](
        method="GET",
        headers={},
        path_parts=["start_oauth"],
        query={
            "error": ["access_denied"],
            "error_description": ["The user denied access"],
            "state": [state],
        },
        body=None,
        asset=asset,
        soar_base_url="https://soar.example.com",
        soar_auth_token="token",
        asset_id=123,
    )


def test_oauth_error_callback_rejects_invalid_state_without_mutating_auth_state():
    asset = _asset_with_pending_oauth_session("expected-state")
    original_state = asset.auth_state.get_all()

    response = oauth_callback(_error_callback_request(asset, "invalid-state"))

    assert response.status_code == 400
    assert response.content == "Invalid OAuth state"
    assert asset.auth_state.get_all() == original_state


def test_oauth_error_callback_records_error_after_state_validation():
    asset = _asset_with_pending_oauth_session("expected-state")

    response = oauth_callback(_error_callback_request(asset, "expected-state"))

    assert response.status_code == 400
    assert response.content == "Authorization failed: The user denied access"
    assert asset.auth_state[AUTHORIZATION_ERROR_STATE_KEY] == (
        "Salesforce authorization failed: access_denied. The user denied access"
    )
