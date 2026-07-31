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
    OAuthBearerAuth,
    OAuthConfig,
    OAuthToken,
    StaticTokenAuth,
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
SALESFORCE_INSTANCE_DOMAIN = ".salesforce.com"
SALESFORCE_MY_DOMAIN = ".my.salesforce.com"


def _trusted_instance_origin(instance_url: object) -> str | None:
    """Return a normalized Salesforce origin, or None when the URL is untrusted."""
    if not isinstance(instance_url, str):
        return None

    try:
        parsed = urlparse(instance_url)
        port = parsed.port
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not host.endswith(SALESFORCE_INSTANCE_DOMAIN)
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return None

    return f"https://{host}"


def _configured_my_domain_origin(domain_url: str | None) -> str:
    """Validate and normalize the My Domain URL used by client credentials."""
    candidate = (domain_url or "").strip()
    if not candidate:
        raise ActionFailure(
            "My Domain URL must be set when using Client Credentials flow."
        )
    if "://" not in candidate:
        candidate = f"https://{candidate}"

    origin = _trusted_instance_origin(candidate)
    if not origin or not urlparse(origin).hostname.endswith(SALESFORCE_MY_DOMAIN):
        raise ActionFailure(
            "My Domain URL must be a full HTTPS URL ending in .my.salesforce.com."
        )
    return origin


def get_oauth_client(asset: Asset) -> SOARAssetOAuthClient:
    """Return the SDK OAuth client used for callbacks and token refresh."""
    token_endpoint = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
    config = OAuthConfig(
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=token_endpoint,
    )
    return SOARAssetOAuthClient(config, asset.auth_state)


def get_authorization_code_flow(
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


def get_client_credentials_flow(asset: Asset) -> ClientCredentialsFlow:
    origin = _configured_my_domain_origin(asset.domain_url)
    token_endpoint = f"{origin}/services/oauth2/token"
    return ClientCredentialsFlow(
        auth_state=asset.auth_state,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=token_endpoint,
    )


def authenticate_client_credentials(asset: Asset) -> None:
    """Obtain and store an access token via the Client Credentials flow."""
    flow = get_client_credentials_flow(asset)
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

    store_token(asset, OAuthToken.model_validate(resp_json))
    logger.info("Successfully obtained access token via username-password flow")


def get_request_auth(asset: Asset) -> httpx.Auth:
    """Return SDK-backed HTTP authentication for the configured grant type."""
    if asset.use_client_credentials:
        try:
            flow = get_client_credentials_flow(asset)
            token = flow.get_token()
            return StaticTokenAuth(token)
        except OAuthClientError as e:
            raise ActionFailure(str(e)) from e

    return OAuthBearerAuth(get_oauth_client(asset))


def get_instance_url(asset: Asset) -> str:
    """Return a normalized, trusted Salesforce instance origin."""
    token = _load_token(asset)
    if not token:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    instance_url = token.model_extra.get("instance_url") if token.model_extra else None
    if not instance_url and asset.use_client_credentials:
        instance_url = _configured_my_domain_origin(asset.domain_url)
    if not instance_url:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    origin = _trusted_instance_origin(instance_url)
    if not origin:
        raise ActionFailure(
            "OAuth token response returned an untrusted Salesforce instance URL."
        )
    return origin


def store_token(asset: Asset, token: OAuthToken) -> None:
    """Persist a token while preserving other SDK-managed auth state."""
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
