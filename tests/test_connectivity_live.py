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
