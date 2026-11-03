# Copyright (c) 2026 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from src.asset import Asset
from src.auth import (
    get_authorization_endpoint,
    get_oauth_token_endpoint,
    get_token_endpoint,
)


def _asset(**overrides: object) -> Asset:
    configuration = {
        "client_id": "client-id",
        "client_secret": "client-secret",  # pragma: allowlist secret
        "domain_url": "D3T000003XSQYEAY-dev-ed.my.salesforce.com/",
        "use_client_credentials": False,
        "username": None,
        "password": None,
        "is_test_environment": False,
    }
    configuration.update(overrides)
    return Asset.model_validate(configuration)


def test_authorization_code_endpoints_use_my_domain() -> None:
    asset = _asset()

    assert get_authorization_endpoint(asset) == (
        "https://d3t000003xsqyeay-dev-ed.my.salesforce.com/services/oauth2/authorize"
    )
    assert get_oauth_token_endpoint(asset) == (
        "https://d3t000003xsqyeay-dev-ed.my.salesforce.com/services/oauth2/token"
    )


def test_username_password_token_endpoint_retains_legacy_login_origin() -> None:
    asset = _asset(
        username="username",
        password="password-with-security-token",
        is_test_environment=True,
    )

    assert get_token_endpoint(asset) == "https://test.salesforce.com/services/oauth2/token"
