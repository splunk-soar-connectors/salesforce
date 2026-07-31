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

from soar_sdk.auth.client import OAuthClientError
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from .asset import Asset
from .auth import (
    authenticate_client_credentials,
    authenticate_username_password,
    get_authorization_code_flow,
    get_instance_url,
    get_request_auth,
    store_token,
)


logger = getLogger()
SALESFORCE_DEFAULT_TIMEOUT = 30


def _latest_api_version(versions: object) -> str:
    if not isinstance(versions, list) or not versions:
        raise ActionFailure(
            "Salesforce returned an empty or unexpected response for API versions."
        )
    latest = versions[-1]
    if not isinstance(latest, dict) or not latest.get("url"):
        raise ActionFailure(
            "Salesforce API version response is missing the 'url' field."
        )
    return str(latest["url"])


def _authenticate_with_browser(asset: Asset, redirect_uri: str) -> None:
    flow = get_authorization_code_flow(asset, redirect_uri)
    auth_url = flow.get_authorization_url()
    logger.info(f"To continue, open this link in a new tab:\n {auth_url}")
    try:
        token = flow.wait_for_authorization()
    except OAuthClientError as e:
        raise ActionFailure(str(e)) from e

    # SDK 3.25.x clears the newly stored token while cleaning up the OAuth
    # session, so persist the returned token once after the flow completes.
    store_token(asset, token)
    logger.info("Successfully obtained tokens via authorization code flow")


def run_test_connectivity(asset: Asset, *, oauth_callback_url: str) -> None:
    """Authenticate with the configured grant and verify Salesforce API access."""
    if asset.use_client_credentials:
        authenticate_client_credentials(asset)
    elif asset.username and asset.password:
        authenticate_username_password(asset)
    else:
        _authenticate_with_browser(asset, oauth_callback_url)

    logger.info("Obtaining Salesforce API version")
    try:
        response = httpx.get(
            get_instance_url(asset) + "/services/data/",
            auth=get_request_auth(asset),
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=bool(asset.verify_ssl),
        )
        response.raise_for_status()
        latest = _latest_api_version(response.json())
    except ActionFailure:
        raise
    except Exception as e:
        raise ActionFailure(f"Connected but failed to fetch API version: {e}") from e

    asset.cache_state["latest_version"] = latest
    logger.info(f"Latest Salesforce API version: {latest}")
