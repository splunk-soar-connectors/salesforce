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
from urllib.parse import urlparse

import httpx

from soar_sdk.auth import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
    OAuthConfig,
    OAuthToken,
)
from soar_sdk.auth.client import OAuthClientError, SOARAssetOAuthClient
from soar_sdk.auth.models import OAuthState
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger

from .asset import Asset

logger = getLogger()

URL_GET_CODE = "https://login.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN = "https://login.salesforce.com/services/oauth2/token"  # noqa: S105
URL_GET_CODE_TEST = "https://test.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN_TEST = "https://test.salesforce.com/services/oauth2/token"  # noqa: S105

SALESFORCE_DEFAULT_TIMEOUT = 30


def get_oauth_client(asset: Asset) -> SOARAssetOAuthClient:
    """Return the SDK OAuth client used for callbacks and token refresh."""
    token_endpoint = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
    config = OAuthConfig(
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=token_endpoint,
    )
    return SOARAssetOAuthClient(config, asset.auth_state)


def _build_authorization_code_flow(
    asset: Asset, redirect_uri: str
) -> AuthorizationCodeFlow:
    if asset.is_test_environment:
        auth_endpoint = URL_GET_CODE_TEST
        token_endpoint = URL_GET_TOKEN_TEST
    else:
        auth_endpoint = URL_GET_CODE
        token_endpoint = URL_GET_TOKEN

    return AuthorizationCodeFlow(
        auth_state=asset.auth_state,
        asset_id=asset.auth_state.asset_id,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=auth_endpoint,
        token_endpoint=token_endpoint,
        redirect_uri=redirect_uri,
        use_pkce=True,
    )


def _build_client_credentials_flow(asset: Asset) -> ClientCredentialsFlow:
    domain_url = (asset.domain_url or "").strip()
    if not domain_url:
        raise ActionFailure(
            "My Domain URL must be set when using Client Credentials flow."
        )
    if "://" not in domain_url:
        domain_url = f"https://{domain_url}"
    parsed = urlparse(domain_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ActionFailure(
            "My Domain URL must be a full HTTPS URL, e.g. https://example.my.salesforce.com"
        )
    if not parsed.netloc.lower().endswith(".my.salesforce.com"):
        raise ActionFailure(
            "My Domain URL must end in .my.salesforce.com. Do not use login.salesforce.com or test.salesforce.com."
        )

    token_endpoint = f"{parsed.scheme}://{parsed.netloc}/services/oauth2/token"
    return ClientCredentialsFlow(
        auth_state=asset.auth_state,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=token_endpoint,
    )


def authenticate_client_credentials(asset: Asset) -> None:
    """Obtain and store an access token via the Client Credentials flow."""
    flow = _build_client_credentials_flow(asset)
    flow.authenticate()
    logger.info("Successfully obtained access token via client credentials flow")


def authenticate_username_password(asset: Asset) -> None:
    """Obtain and store an access token via the legacy username-password flow.

    The password grant is not supported by the SDK flows, so we call the
    token endpoint directly and store the result in OAuthState so that
    get_access_token/get_instance_url can read it uniformly.
    """
    token_url = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
    verify_ssl = bool(asset.verify_ssl)
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "username": asset.username,
                "password": asset.password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=verify_ssl,
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token request failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(
            f"Salesforce rejected credentials: {resp_json.get('error_description') or resp_json['error']}"
        )

    _store_token(asset, OAuthToken.model_validate(resp_json))
    logger.info("Successfully obtained access token via username-password flow")


def start_oauth_flow(asset: Asset, redirect_uri: str) -> str:
    """Begin the Authorization Code (PKCE) flow. Returns the URL the user must visit."""
    flow = _build_authorization_code_flow(asset, redirect_uri)
    return flow.get_authorization_url()


def wait_for_oauth_and_finalize(asset: Asset, redirect_uri: str) -> None:
    """Poll until the user completes browser auth, then exchange the code for a token.

    The SDK's fetch_token_with_authorization_code saves the token and then overwrites
    auth_state with the old session-cleanup state, losing the token. We re-store the
    returned token to fix that.
    """
    flow = _build_authorization_code_flow(asset, redirect_uri)
    try:
        token = flow.wait_for_authorization()
    except OAuthClientError as e:
        raise ActionFailure(str(e)) from e
    _store_token(asset, token)
    logger.info("Successfully obtained tokens via authorization code flow")


def get_access_token(asset: Asset) -> str:
    """Return a valid access token, refreshing via SDK flows when possible."""
    if asset.use_client_credentials:
        try:
            flow = _build_client_credentials_flow(asset)
            token = flow.get_token()
            return token.access_token
        except OAuthClientError as e:
            raise ActionFailure(str(e)) from e

    # For auth-code and username-password flows, read from OAuthState
    token = _load_token(asset)
    if not token:
        raise ActionFailure("No access token found. Re-run test connectivity.")

    if token.is_expired():
        if token.refresh_token:
            try:
                token_url = (
                    URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
                )
                config = OAuthConfig(
                    client_id=asset.client_id,
                    client_secret=asset.client_secret,
                    token_endpoint=token_url,
                )
                token = SOARAssetOAuthClient(config, asset.auth_state).refresh_token(
                    token.refresh_token
                )
            except OAuthClientError as e:
                raise ActionFailure(f"Token refresh failed: {e}") from e
        else:
            raise ActionFailure("Access token has expired. Re-run test connectivity.")

    return token.access_token


def get_instance_url(asset: Asset) -> str:
    """Return the Salesforce instance URL from the stored token."""
    token = _load_token(asset)
    if not token:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    instance_url = token.model_extra.get("instance_url") if token.model_extra else None
    if not instance_url:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    return instance_url


def _store_token(asset: Asset, token: OAuthToken) -> None:
    """Write an OAuthToken into the SDK's OAuthState structure."""
    state = OAuthState(token=token, client_id=asset.client_id)
    current = asset.auth_state.get_all()
    current["oauth"] = state.model_dump(mode="json", exclude_none=True)
    asset.auth_state.put_all(current)


def _load_token(asset: Asset) -> OAuthToken | None:
    """Read the OAuthToken from the SDK's OAuthState structure."""
    state_data = asset.auth_state.get_all()
    oauth_data = state_data.get("oauth")
    if not oauth_data:
        return None
    return OAuthState.model_validate(oauth_data).token
