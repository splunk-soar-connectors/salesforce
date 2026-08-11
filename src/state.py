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

from .asset import Asset


POLL_OFFSET_STATE_KEY = "cur_offset"
CONTAINER_SDI_SALT_STATE_KEY = "container_source_data_identifier_salt"
LEGACY_POLL_STATE_KEYS = (
    POLL_OFFSET_STATE_KEY,
    CONTAINER_SDI_SALT_STATE_KEY,
)


def migrate_legacy_poll_state(asset: Asset) -> None:
    """Move flat legacy polling state into the SDK ingest partition."""
    backend = asset.ingest_state.backend
    legacy_state = backend.load_state() or {}
    if not isinstance(legacy_state, dict):
        raise ValueError("Salesforce asset state has an unexpected format")

    ingest_state = asset.ingest_state.get_all()
    migrated_keys: list[str] = []

    if (
        POLL_OFFSET_STATE_KEY not in ingest_state
        and POLL_OFFSET_STATE_KEY in legacy_state
    ):
        ingest_state[POLL_OFFSET_STATE_KEY] = legacy_state[POLL_OFFSET_STATE_KEY]
        migrated_keys.append(POLL_OFFSET_STATE_KEY)

    salt = ingest_state.get(CONTAINER_SDI_SALT_STATE_KEY)
    if not isinstance(salt, str) or not salt:
        legacy_salt = legacy_state.get(CONTAINER_SDI_SALT_STATE_KEY)
        if isinstance(legacy_salt, str) and legacy_salt:
            salt = legacy_salt
            migrated_keys.append(CONTAINER_SDI_SALT_STATE_KEY)
        else:
            salt = secrets.token_urlsafe(32)
        ingest_state[CONTAINER_SDI_SALT_STATE_KEY] = salt

    asset.ingest_state.put_all(ingest_state)

    cleaned_state = backend.load_state() or {}
    if not isinstance(cleaned_state, dict):
        raise ValueError("Salesforce asset state has an unexpected format")
    removed_legacy_key = False
    for key in LEGACY_POLL_STATE_KEYS:
        if key in cleaned_state:
            cleaned_state.pop(key)
            removed_legacy_key = True
    if removed_legacy_key:
        backend.save_state(cleaned_state)

    if migrated_keys:
        logging.info(
            f"Migrated legacy Salesforce polling state: {', '.join(migrated_keys)}"
        )
