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
import pytest
from soar_sdk.auth import OAuthToken
from soar_sdk.auth.models import OAuthState
from soar_sdk.crypto import encrypt

from src.asset import Asset
from src.state import migrate_legacy_state
from src.test_connectivity import API_VERSIONS_PATH, run_test_connectivity


@pytest.mark.live
def test_client_credentials_test_connectivity_live(asset: Asset) -> None:
    run_test_connectivity(asset)

    latest_version = asset.cache_state["latest_version"]
    assert isinstance(latest_version, str)
    assert latest_version.startswith(API_VERSIONS_PATH)


@pytest.mark.live
def test_migrate_legacy_state_live(asset: Asset) -> None:
    backend = asset.ingest_state.backend
    original_state = backend.load_state() or {}
    legacy_refresh_token = "legacy-salesforce-refresh-token"
    legacy_latest_version = "/services/data/v65.0"
    legacy_offset = 137
    legacy_salt = "legacy-salesforce-container-salt"

    try:
        legacy_state = dict(original_state)
        legacy_state.pop("auth", None)
        legacy_state.pop("cache", None)
        legacy_state.pop("ingest", None)
        legacy_state["refresh_token"] = encrypt(
            legacy_refresh_token, asset.auth_state.asset_id
        )
        legacy_state["latest_version"] = legacy_latest_version
        legacy_state["cur_offset"] = legacy_offset
        legacy_state["container_source_data_identifier_salt"] = legacy_salt
        backend.save_state(legacy_state)

        migrate_legacy_state(asset)

        oauth_state = OAuthState.model_validate(asset.auth_state["oauth"])
        assert oauth_state.client_id == asset.client_id
        assert oauth_state.token is not None
        assert oauth_state.token.access_token == ""
        assert oauth_state.token.refresh_token == legacy_refresh_token
        assert oauth_state.token.expires_at == 0
        assert asset.cache_state["latest_version"] == legacy_latest_version
        assert asset.ingest_state["cur_offset"] == legacy_offset
        assert (
            asset.ingest_state["container_source_data_identifier_salt"] == legacy_salt
        )
        migrated_state = backend.load_state() or {}
        for key in (
            "refresh_token",
            "latest_version",
            "cur_offset",
            "container_source_data_identifier_salt",
        ):
            assert key not in migrated_state

        state_after_migration = dict(migrated_state)
        migrate_legacy_state(asset)
        assert backend.load_state() == state_after_migration

        sdk_token = OAuthToken(
            access_token="sdk-access-token",
            refresh_token="sdk-refresh-token",
            expires_at=4_102_444_800,
        )
        sdk_oauth_state = OAuthState(token=sdk_token, client_id=asset.client_id)
        asset.auth_state.put_all(
            {"oauth": sdk_oauth_state.model_dump(mode="json", exclude_none=True)}
        )
        asset.cache_state.put_all({"latest_version": "/services/data/v66.0"})
        asset.ingest_state.put_all(
            {
                "cur_offset": 211,
                "container_source_data_identifier_salt": "sdk-salt",
            }
        )

        stale_legacy_state = backend.load_state() or {}
        stale_legacy_state["refresh_token"] = encrypt(
            "stale-refresh-token", asset.auth_state.asset_id
        )
        stale_legacy_state["latest_version"] = "/services/data/v1.0"
        stale_legacy_state["cur_offset"] = 999
        stale_legacy_state["container_source_data_identifier_salt"] = "stale-salt"
        backend.save_state(stale_legacy_state)

        migrate_legacy_state(asset)

        current_oauth_state = OAuthState.model_validate(asset.auth_state["oauth"])
        assert current_oauth_state == sdk_oauth_state
        assert asset.cache_state["latest_version"] == "/services/data/v66.0"
        assert asset.ingest_state["cur_offset"] == 211
        assert asset.ingest_state["container_source_data_identifier_salt"] == "sdk-salt"
        cleaned_state = backend.load_state() or {}
        for key in (
            "refresh_token",
            "latest_version",
            "cur_offset",
            "container_source_data_identifier_salt",
        ):
            assert key not in cleaned_state
    finally:
        backend.save_state(original_state)


@pytest.mark.live
def test_migrate_legacy_ingest_state_survives_transaction_rollback_live(
    asset: Asset,
) -> None:
    backend = asset.ingest_state.backend
    original_state = backend.load_state() or {}

    try:
        legacy_state = dict(original_state)
        legacy_state.pop("ingest", None)
        legacy_state["cur_offset"] = 137
        legacy_state["container_source_data_identifier_salt"] = "legacy-salt"
        backend.save_state(legacy_state)

        asset.ingest_state.begin_transaction()
        migrate_legacy_state(asset)
        asset.ingest_state.rollback()

        assert asset.ingest_state["cur_offset"] == 137
        assert (
            asset.ingest_state["container_source_data_identifier_salt"] == "legacy-salt"
        )
        migrated_state = backend.load_state() or {}
        assert "cur_offset" not in migrated_state
        assert "container_source_data_identifier_salt" not in migrated_state
    finally:
        if asset.ingest_state.in_transaction:
            asset.ingest_state.rollback()
        backend.save_state(original_state)
