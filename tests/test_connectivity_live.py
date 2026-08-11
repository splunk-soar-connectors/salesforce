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

from src.asset import Asset
from src.test_connectivity import API_VERSIONS_PATH, run_test_connectivity


@pytest.mark.live
def test_client_credentials_test_connectivity_live(asset: Asset) -> None:
    run_test_connectivity(asset)

    latest_version = asset.cache_state["latest_version"]
    assert isinstance(latest_version, str)
    assert latest_version.startswith(API_VERSIONS_PATH)


@pytest.mark.live
def test_test_connectivity_migrates_legacy_poll_state_live(asset: Asset) -> None:
    backend = asset.ingest_state.backend
    original_state = backend.load_state() or {}
    legacy_offset = 137
    legacy_salt = "legacy-salesforce-container-salt"

    try:
        legacy_state = dict(original_state)
        legacy_state.pop("ingest", None)
        legacy_state["cur_offset"] = legacy_offset
        legacy_state["container_source_data_identifier_salt"] = legacy_salt
        backend.save_state(legacy_state)

        run_test_connectivity(asset)

        assert asset.ingest_state["cur_offset"] == legacy_offset
        assert (
            asset.ingest_state["container_source_data_identifier_salt"] == legacy_salt
        )
        migrated_state = backend.load_state() or {}
        assert "cur_offset" not in migrated_state
        assert "container_source_data_identifier_salt" not in migrated_state

        migrated_state["cur_offset"] = 999
        migrated_state["container_source_data_identifier_salt"] = "stale-salt"
        backend.save_state(migrated_state)

        run_test_connectivity(asset)

        assert asset.ingest_state["cur_offset"] == legacy_offset
        assert (
            asset.ingest_state["container_source_data_identifier_salt"] == legacy_salt
        )
        cleaned_state = backend.load_state() or {}
        assert "cur_offset" not in cleaned_state
        assert "container_source_data_identifier_salt" not in cleaned_state
    finally:
        backend.save_state(original_state)
