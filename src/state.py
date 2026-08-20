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
    """Persist migration values even during an SDK-managed state transaction."""
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


def migrate_legacy_state(asset: Asset) -> None:
    """Move flat legacy state into SDK-managed state partitions."""
    backend = asset.auth_state.backend
    legacy_state = backend.load_state() or {}
    if not isinstance(legacy_state, dict):
        raise ValueError("Salesforce asset state has an unexpected format")

    auth_state = asset.auth_state.get_all()
    cache_state = asset.cache_state.get_all()
    ingest_state = asset.ingest_state.get_all()

    auth_changed = False
    cache_changed = False
    ingest_changed = False
    removable_keys: set[str] = set()
    migrated_keys: list[str] = []

    if LEGACY_REFRESH_TOKEN_STATE_KEY in legacy_state:
        oauth_state = OAuthState.model_validate(auth_state.get("oauth") or {})
        if oauth_state.token is None:
            encrypted_refresh_token = legacy_state[LEGACY_REFRESH_TOKEN_STATE_KEY]
            if not isinstance(encrypted_refresh_token, str):
                raise ValueError(
                    "Legacy Salesforce refresh token has an unexpected format"
                )
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

            oauth_state.token = OAuthToken(
                access_token="",
                refresh_token=refresh_token,
                expires_at=0,
            )
            oauth_state.client_id = asset.client_id
            auth_state["oauth"] = oauth_state.model_dump(mode="json", exclude_none=True)
            auth_changed = True
            migrated_keys.append(LEGACY_REFRESH_TOKEN_STATE_KEY)
        removable_keys.add(LEGACY_REFRESH_TOKEN_STATE_KEY)

    if LATEST_VERSION_STATE_KEY in legacy_state:
        if LATEST_VERSION_STATE_KEY not in cache_state:
            latest_version = legacy_state[LATEST_VERSION_STATE_KEY]
            if not isinstance(latest_version, str) or not latest_version.startswith(
                "/services/data/"
            ):
                raise ValueError(
                    "Legacy Salesforce API version has an unexpected format"
                )
            cache_state[LATEST_VERSION_STATE_KEY] = latest_version
            cache_changed = True
            migrated_keys.append(LATEST_VERSION_STATE_KEY)
        removable_keys.add(LATEST_VERSION_STATE_KEY)

    if (
        POLL_OFFSET_STATE_KEY not in ingest_state
        and POLL_OFFSET_STATE_KEY in legacy_state
    ):
        ingest_state[POLL_OFFSET_STATE_KEY] = legacy_state[POLL_OFFSET_STATE_KEY]
        ingest_changed = True
        migrated_keys.append(POLL_OFFSET_STATE_KEY)
    if POLL_OFFSET_STATE_KEY in legacy_state:
        removable_keys.add(POLL_OFFSET_STATE_KEY)

    salt = ingest_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    if not isinstance(salt, str) or not salt:
        legacy_salt = legacy_state.get(CONTAINER_SDI_SALT_STATE_KEY)
        if isinstance(legacy_salt, str) and legacy_salt:
            salt = legacy_salt
            migrated_keys.append(CONTAINER_SDI_SALT_STATE_KEY)
        else:
            salt = secrets.token_urlsafe(32)
        ingest_state[CONTAINER_SDI_SALT_STATE_KEY] = salt
        ingest_changed = True
    if CONTAINER_SDI_SALT_STATE_KEY in legacy_state:
        removable_keys.add(CONTAINER_SDI_SALT_STATE_KEY)

    if auth_changed:
        _put_state_durably(asset.auth_state, auth_state)
    if cache_changed:
        _put_state_durably(asset.cache_state, cache_state)
    if ingest_changed:
        _put_state_durably(asset.ingest_state, ingest_state)

    cleaned_state = backend.load_state() or {}
    if not isinstance(cleaned_state, dict):
        raise ValueError("Salesforce asset state has an unexpected format")
    removed_legacy_key = False
    for key in removable_keys:
        if key in cleaned_state:
            cleaned_state.pop(key)
            removed_legacy_key = True
    if removed_legacy_key:
        backend.save_state(cleaned_state)

    if migrated_keys:
        logging.info(f"Migrated legacy Salesforce state: {', '.join(migrated_keys)}")
