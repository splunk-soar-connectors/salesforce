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
import secrets

from soar_sdk import logging
from soar_sdk.asset_state import AssetState
from soar_sdk.auth import OAuthToken
from soar_sdk.auth.models import OAuthState
from soar_sdk.crypto import decrypt

from .asset import Asset


LEGACY_REFRESH_TOKEN_STATE_KEY = "refresh_token"  # noqa: S105  # pragma: allowlist secret
LATEST_VERSION_STATE_KEY = "latest_version"
POLL_OFFSET_STATE_KEY = "cur_offset"
CONTAINER_SDI_SALT_STATE_KEY = "container_source_data_identifier_salt"


def _put_state_durably(state: AssetState, value: dict[str, object]) -> None:
    """Persist values even during an SDK-managed state transaction."""
    if not state.in_transaction:
        state.put_all(value)
        return

    durable_state = AssetState(
        state.backend,
        state.state_key,
        state.asset_id,
        app_id=state.app_id,
        encrypted=state.encrypted,
    )
    durable_state.put_all(value)
    state.put_all(value)


def persist_poll_offset(asset: Asset, offset: int) -> None:
    """Persist a retry offset even when the current poll transaction rolls back."""
    ingest_state = asset.ingest_state.get_all()
    ingest_state[POLL_OFFSET_STATE_KEY] = offset
    _put_state_durably(asset.ingest_state, ingest_state)


def _load_legacy_state(asset: Asset) -> dict[str, object]:
    backend = asset.auth_state.backend
    legacy_state = backend.load_state() or {}
    if not isinstance(legacy_state, dict):
        raise ValueError("Salesforce asset state has an unexpected format")
    return legacy_state


def migrate_legacy_oauth_state(asset: Asset) -> None:
    """Seed SDK OAuth state only when a legacy refresh token is needed."""
    auth_state = asset.auth_state.get_all()
    oauth_state = OAuthState.model_validate(auth_state.get("oauth") or {})
    if oauth_state.token is not None and oauth_state.token.refresh_token:
        return

    legacy_state = _load_legacy_state(asset)
    if LEGACY_REFRESH_TOKEN_STATE_KEY not in legacy_state:
        return

    encrypted_refresh_token = legacy_state[LEGACY_REFRESH_TOKEN_STATE_KEY]
    if not isinstance(encrypted_refresh_token, str):
        raise ValueError("Legacy Salesforce refresh token has an unexpected format")
    try:
        refresh_token = decrypt(
            encrypted_refresh_token,
            asset.auth_state.asset_id,
        )
    except Exception as error:
        raise ValueError(
            "Unable to decrypt the legacy Salesforce refresh token"
        ) from error
    if not refresh_token:
        raise ValueError("Legacy Salesforce refresh token is empty")

    # Re-read immediately before writing so SDK state established by another
    # invocation takes precedence. The SDK does not currently expose a
    # conditional state update, so this narrows but cannot eliminate that race.
    auth_state = asset.auth_state.get_all()
    oauth_state = OAuthState.model_validate(auth_state.get("oauth") or {})
    if oauth_state.token is not None and oauth_state.token.refresh_token:
        return

    if oauth_state.token is None:
        oauth_state.token = OAuthToken(
            access_token="",
            refresh_token=refresh_token,
            expires_at=0,
        )
    else:
        oauth_state.token = oauth_state.token.model_copy(
            update={"refresh_token": refresh_token}
        )
    oauth_state.client_id = asset.client_id
    auth_state["oauth"] = oauth_state.model_dump(mode="json", exclude_none=True)
    asset.auth_state.put_all(auth_state)
    logging.info("Migrated legacy Salesforce state: refresh_token")


def get_latest_api_version(asset: Asset) -> object:
    """Return the SDK-cached API version, lazily importing the legacy value."""
    cache_state = asset.cache_state.get_all()
    if LATEST_VERSION_STATE_KEY in cache_state:
        return cache_state[LATEST_VERSION_STATE_KEY]

    legacy_state = _load_legacy_state(asset)
    if LATEST_VERSION_STATE_KEY not in legacy_state:
        return None

    latest_version = legacy_state[LATEST_VERSION_STATE_KEY]
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ValueError("Legacy Salesforce API version has an unexpected format")

    cache_state = asset.cache_state.get_all()
    if LATEST_VERSION_STATE_KEY in cache_state:
        return cache_state[LATEST_VERSION_STATE_KEY]

    cache_state[LATEST_VERSION_STATE_KEY] = latest_version
    asset.cache_state.put_all(cache_state)
    logging.info("Migrated legacy Salesforce state: latest_version")
    return latest_version


def migrate_legacy_ingest_state(asset: Asset) -> None:
    """Seed missing SDK ingest values when polling first needs them."""
    ingest_state = asset.ingest_state.get_all()
    salt = ingest_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    needs_offset = POLL_OFFSET_STATE_KEY not in ingest_state
    needs_salt = not isinstance(salt, str) or not salt
    if not needs_offset and not needs_salt:
        return

    legacy_state = _load_legacy_state(asset)
    legacy_offset = legacy_state.get(POLL_OFFSET_STATE_KEY)
    legacy_salt = legacy_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    candidate_salt = (
        legacy_salt
        if isinstance(legacy_salt, str) and legacy_salt
        else secrets.token_urlsafe(32)
    )

    ingest_state = asset.ingest_state.get_all()
    migrated_keys: list[str] = []
    changed = False
    if (
        POLL_OFFSET_STATE_KEY not in ingest_state
        and POLL_OFFSET_STATE_KEY in legacy_state
    ):
        ingest_state[POLL_OFFSET_STATE_KEY] = legacy_offset
        migrated_keys.append(POLL_OFFSET_STATE_KEY)
        changed = True

    current_salt = ingest_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    if not isinstance(current_salt, str) or not current_salt:
        ingest_state[CONTAINER_SDI_SALT_STATE_KEY] = candidate_salt
        if isinstance(legacy_salt, str) and legacy_salt:
            migrated_keys.append(CONTAINER_SDI_SALT_STATE_KEY)
        changed = True

    if changed:
        _put_state_durably(asset.ingest_state, ingest_state)
    if migrated_keys:
        logging.info(f"Migrated legacy Salesforce state: {', '.join(migrated_keys)}")
