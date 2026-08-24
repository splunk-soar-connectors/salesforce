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
from soar_sdk import logging
from soar_sdk.auth import AuthorizationCodeFlow, OAuthToken, StaticTokenAuth

from .asset import Asset
from .auth import get_auth_flow, get_instance_origin, store_token
from .webhooks.oauth import AUTHORIZATION_ERROR_STATE_KEY


SALESFORCE_DEFAULT_TIMEOUT = 30.0
API_VERSIONS_PATH = "/services/data/"
INVALID_API_VERSIONS_ERROR = (
    "Salesforce returned an empty or unexpected API versions response"
)
INVALID_LATEST_API_ERROR = (
    "Salesforce API versions response is missing a valid latest API URL"
)


def get_latest_api_path(versions: object) -> str:
    if not isinstance(versions, list) or not versions:
        raise ValueError(INVALID_API_VERSIONS_ERROR)

    latest = versions[-1]
    if not isinstance(latest, dict):
        raise ValueError(INVALID_LATEST_API_ERROR)

    latest_url = latest.get("url")
    if not isinstance(latest_url, str) or not latest_url.startswith(API_VERSIONS_PATH):
        raise ValueError(INVALID_LATEST_API_ERROR)
    return latest_url


def authenticate_with_browser(
    asset: Asset,
    flow: AuthorizationCodeFlow,
) -> OAuthToken:
    asset.auth_state.pop(AUTHORIZATION_ERROR_STATE_KEY, None)
    authorization_url = flow.get_authorization_url()

    logging.info("To continue, open this link in a new browser tab:")
    logging.info(authorization_url)  # nosemgrep

    def report_progress(_iteration: int) -> None:
        auth_state = asset.auth_state.get_all(force_reload=True)
        if authorization_error := auth_state.get(AUTHORIZATION_ERROR_STATE_KEY):
            raise ValueError(str(authorization_error))
        logging.progress("Waiting for Salesforce authorization...")

    token = flow.wait_for_authorization(on_progress=report_progress)

    # TODO: Revisit and remove this workaround after splunk-soar-sdk fixes
    # authorization-code token persistence during OAuth session cleanup.
    # splunk-soar-sdk 3.28.1 clears the newly stored token while cleaning up
    # the OAuth session after code exchange. Persist the returned token once.
    store_token(asset, token)
    logging.info("Successfully obtained token through authorization code flow")
    return token


def verify_salesforce_access(asset: Asset, token: OAuthToken) -> None:
    instance_origin = get_instance_origin(asset, token)

    logging.info("Obtaining Salesforce API version")
    with httpx.Client(
        base_url=instance_origin,
        auth=StaticTokenAuth(token),
        timeout=SALESFORCE_DEFAULT_TIMEOUT,
    ) as client:
        response = client.get(API_VERSIONS_PATH)
        response.raise_for_status()
        latest_api_path = get_latest_api_path(response.json())

        logging.info("Testing latest API version")
        response = client.get(latest_api_path)
        response.raise_for_status()

    asset.cache_state["latest_version"] = latest_api_path


def run_test_connectivity(
    asset: Asset,
    *,
    oauth_callback_url: str | None = None,
) -> None:
    logging.info("Testing connectivity. Connecting...")
    logging.info("Generating access token")
    flow = get_auth_flow(asset, redirect_uri=oauth_callback_url)
    if isinstance(flow, AuthorizationCodeFlow):
        token = authenticate_with_browser(asset, flow)
    else:
        token = flow.authenticate()

    verify_salesforce_access(asset, token)
    logging.info("Test Connectivity Passed")
