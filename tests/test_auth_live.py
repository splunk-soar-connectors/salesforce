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
import requests
import pytest
from soar_sdk.auth import ClientCredentialsFlow

from src.asset import Asset
from src.auth import (
    get_auth_flow,
    get_token_instance_origin,
    normalize_my_domain_url,
)


@pytest.mark.live
def test_client_credentials_authentication_live(asset: Asset) -> None:
    flow = get_auth_flow(asset)

    assert isinstance(flow, ClientCredentialsFlow)
    token = flow.authenticate()
    instance_origin = get_token_instance_origin(
        token,
        fallback_url=normalize_my_domain_url(asset.domain_url),
    )

    response = requests.get(
        f"{instance_origin}/services/data/",
        headers={"Authorization": f"Bearer {token.access_token}"},
        timeout=30,
    )
    response.raise_for_status()

    versions = response.json()
    assert isinstance(versions, list)
    assert versions
