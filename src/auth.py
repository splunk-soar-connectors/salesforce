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
from contextlib import AbstractContextManager
from enum import StrEnum
from urllib.parse import urlparse

import httpx
from soar_sdk.auth import (
    AuthorizationCodeFlow,
    ClientCredentialsFlow,
    OAuthConfig,
    OAuthToken,
    StaticTokenAuth,
    create_oauth_client,
)
from soar_sdk.auth.client import SOARAssetOAuthClient
from soar_sdk.auth.models import OAuthState
from soar_sdk.asset_state import AssetState

from .asset import Asset
from .state import migrate_legacy_oauth_state


SALESFORCE_LOGIN_ORIGIN = "https://login.salesforce.com"
SALESFORCE_TEST_LOGIN_ORIGIN = "https://test.salesforce.com"
SALESFORCE_AUTHORIZATION_PATH = "/services/oauth2/authorize"
SALESFORCE_TOKEN_PATH = "/services/oauth2/token"  # noqa: S105  # pragma: allowlist secret
SALESFORCE_INSTANCE_DOMAIN = ".salesforce.com"
SALESFORCE_MY_DOMAIN = ".my.salesforce.com"
AUTHORIZATION_POLL_TIMEOUT_SECONDS = 300
AUTHORIZATION_POLL_INTERVAL_SECONDS = 5
SALESFORCE_DEFAULT_TIMEOUT = 30.0

MISSING_PASSWORD_ERROR = "Password must be specified with a username"  # noqa: S105  # pragma: allowlist secret
MISSING_USERNAME_ERROR = "Username must be specified for Username Password flow"
MISSING_MY_DOMAIN_ERROR = (
    "My Domain URL must be specified for Client Credentials flow. In Salesforce "
    "Setup, open My Domain and copy the Current My Domain URL (for example, "
    "https://d3t000000example-dev-ed.my.salesforce.com)."
)
INVALID_MY_DOMAIN_ERROR = (
    "My Domain URL must be your Salesforce Current My Domain URL ending in "
    ".my.salesforce.com. Copy only the hostname or HTTPS URL."
)
UNTRUSTED_INSTANCE_ERROR = (
    "OAuth token response returned an untrusted Salesforce instance URL"
)


class AuthMode(StrEnum):
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    USERNAME_PASSWORD = "username_password"  # noqa: S105  # pragma: allowlist secret


def get_auth_mode(asset: Asset) -> AuthMode:
    if asset.use_client_credentials:
        return AuthMode.CLIENT_CREDENTIALS

    if asset.username:
        if not asset.password:
            raise ValueError(MISSING_PASSWORD_ERROR)
        return AuthMode.USERNAME_PASSWORD

    return AuthMode.AUTHORIZATION_CODE


def get_login_origin(asset: Asset) -> str:
    if asset.is_test_environment:
        return SALESFORCE_TEST_LOGIN_ORIGIN
    return SALESFORCE_LOGIN_ORIGIN


def get_authorization_endpoint(asset: Asset) -> str:
    return f"{get_login_origin(asset)}{SALESFORCE_AUTHORIZATION_PATH}"


def get_token_endpoint(asset: Asset) -> str:
    return f"{get_login_origin(asset)}{SALESFORCE_TOKEN_PATH}"


def get_oauth_client(asset: Asset) -> SOARAssetOAuthClient:
    return SOARAssetOAuthClient(
        OAuthConfig(
            client_id=asset.client_id,
            client_secret=asset.client_secret,
            token_endpoint=get_token_endpoint(asset),
        ),
        asset.auth_state,
    )


def normalize_my_domain_url(value: str | None) -> str:
    domain_url = (value or "").strip()
    if not domain_url:
        raise ValueError(MISSING_MY_DOMAIN_ERROR)

    if "://" not in domain_url:
        domain_url = f"https://{domain_url}"

    try:
        parsed = urlparse(domain_url)
        port = parsed.port
    except ValueError as error:
        raise ValueError(INVALID_MY_DOMAIN_ERROR) from error

    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or not host.endswith(SALESFORCE_MY_DOMAIN)
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.path not in ("", "/")
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(INVALID_MY_DOMAIN_ERROR)

    return f"https://{host}"


def get_client_credentials_token_endpoint(asset: Asset) -> str:
    return f"{normalize_my_domain_url(asset.domain_url)}{SALESFORCE_TOKEN_PATH}"


def trusted_instance_origin(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    try:
        parsed = urlparse(value)
        port = parsed.port
    except ValueError:
        return None

    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or not host.endswith(SALESFORCE_INSTANCE_DOMAIN)
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
    ):
        return None

    return f"https://{host}"


def get_token_instance_origin(
    token: OAuthToken,
    *,
    fallback_url: str | None = None,
) -> str:
    token_data = token.model_extra or {}
    instance_url = token_data.get("instance_url") or fallback_url
    instance_origin = trusted_instance_origin(instance_url)
    if instance_origin is None:
        raise ValueError(UNTRUSTED_INSTANCE_ERROR)
    return instance_origin


def get_instance_origin(asset: Asset, token: OAuthToken) -> str:
    fallback_url = (
        normalize_my_domain_url(asset.domain_url)
        if asset.use_client_credentials
        else None
    )
    return get_token_instance_origin(token, fallback_url=fallback_url)


def store_token(asset: Asset, token: OAuthToken) -> None:
    """Persist a token while preserving the SDK-managed OAuth state."""
    current = asset.auth_state.get_all()
    oauth_state = OAuthState.model_validate(current.get("oauth") or {})
    oauth_state.token = token
    oauth_state.client_id = asset.client_id
    current["oauth"] = oauth_state.model_dump(mode="json", exclude_none=True)
    asset.auth_state.put_all(current)


def get_auth_code_flow(
    asset: Asset,
    asset_id: str,
    *,
    redirect_uri: str,
) -> AuthorizationCodeFlow:
    return AuthorizationCodeFlow(
        asset.auth_state,
        asset_id,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        authorization_endpoint=get_authorization_endpoint(asset),
        token_endpoint=get_token_endpoint(asset),
        redirect_uri=redirect_uri,
        use_pkce=True,
        poll_timeout=AUTHORIZATION_POLL_TIMEOUT_SECONDS,
        poll_interval=AUTHORIZATION_POLL_INTERVAL_SECONDS,
    )


def _get_non_browser_auth_state(asset: Asset, auth_mode: AuthMode) -> AssetState:
    return AssetState(
        asset.auth_state.backend,
        f"auth_{auth_mode.value}",
        asset.auth_state.asset_id,
        app_id=asset.auth_state.app_id,
        encrypted=asset.auth_state.encrypted,
    )


def get_client_credentials_flow(asset: Asset) -> ClientCredentialsFlow:
    return ClientCredentialsFlow(
        _get_non_browser_auth_state(asset, AuthMode.CLIENT_CREDENTIALS),
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=get_client_credentials_token_endpoint(asset),
    )


def get_username_password_flow(asset: Asset) -> ClientCredentialsFlow:
    username = asset.username
    if not username:
        raise ValueError(MISSING_USERNAME_ERROR)

    password = asset.password
    if not password:
        raise ValueError(MISSING_PASSWORD_ERROR)

    return ClientCredentialsFlow(
        _get_non_browser_auth_state(asset, AuthMode.USERNAME_PASSWORD),
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=get_token_endpoint(asset),
        extra_params={
            "grant_type": "password",
            "username": username,
            "password": password,
        },
    )


def get_auth_flow(
    asset: Asset,
    *,
    redirect_uri: str | None = None,
) -> AuthorizationCodeFlow | ClientCredentialsFlow:
    auth_mode = get_auth_mode(asset)
    if auth_mode is AuthMode.AUTHORIZATION_CODE:
        if redirect_uri is None:
            raise ValueError("Redirect URI is required for authorization code flow")
        return get_auth_code_flow(
            asset,
            asset.auth_state.asset_id,
            redirect_uri=redirect_uri,
        )
    if auth_mode is AuthMode.CLIENT_CREDENTIALS:
        return get_client_credentials_flow(asset)
    return get_username_password_flow(asset)


def get_access_token(asset: Asset) -> OAuthToken:
    """Return a token appropriate for the asset's configured authentication mode."""
    auth_mode = get_auth_mode(asset)
    if auth_mode is AuthMode.AUTHORIZATION_CODE:
        migrate_legacy_oauth_state(asset)
        return get_oauth_client(asset).get_valid_token(auto_refresh=True)
    return get_auth_flow(asset).authenticate()


def get_salesforce_client(
    asset: Asset,
    *,
    timeout: float = SALESFORCE_DEFAULT_TIMEOUT,
    verify: bool = True,
) -> AbstractContextManager[httpx.Client]:
    """Return an SDK-authenticated client for Salesforce action requests."""
    auth_mode = get_auth_mode(asset)
    token = get_access_token(asset)
    instance_origin = get_instance_origin(asset, token)

    if auth_mode is not AuthMode.AUTHORIZATION_CODE:
        return httpx.Client(
            auth=StaticTokenAuth(token),
            base_url=instance_origin,
            timeout=timeout,
            verify=verify,
        )

    return create_oauth_client(
        asset,
        client_id=asset.client_id,
        client_secret=asset.client_secret,
        token_endpoint=get_token_endpoint(asset),
        base_url=instance_origin,
        timeout=timeout,
        verify=verify,
    )
