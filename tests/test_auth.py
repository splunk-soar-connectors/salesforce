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
from soar_sdk.exceptions import ActionFailure

from src.auth import _configured_my_domain_origin, _trusted_instance_origin
from src.test_connectivity import _latest_api_version


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.my.salesforce.com", "https://example.my.salesforce.com"),
        (
            "https://EXAMPLE.MY.SALESFORCE.COM:443/path?q=1",
            "https://example.my.salesforce.com",
        ),
        (
            "https://example.sandbox.my.salesforce.com",
            "https://example.sandbox.my.salesforce.com",
        ),
    ],
)
def test_trusted_instance_origin_accepts_salesforce_https_origins(
    value: str, expected: str
) -> None:
    assert _trusted_instance_origin(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "http://example.my.salesforce.com",
        "https://salesforce.com",
        "https://salesforce.com.example.org",
        "https://user@example.my.salesforce.com",
        "https://example.my.salesforce.com:8443",
        "https://[not-an-ipv6-address",
    ],
)
def test_trusted_instance_origin_rejects_untrusted_values(value: object) -> None:
    assert _trusted_instance_origin(value) is None


def test_configured_my_domain_origin_adds_https() -> None:
    assert (
        _configured_my_domain_origin("example.my.salesforce.com")
        == "https://example.my.salesforce.com"
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "login.salesforce.com",
        "https://example.salesforce.com",
        "https://example.my.salesforce.com.evil.example",
    ],
)
def test_configured_my_domain_origin_requires_my_domain(value: str | None) -> None:
    with pytest.raises(ActionFailure):
        _configured_my_domain_origin(value)


def test_latest_api_version_returns_last_url() -> None:
    assert (
        _latest_api_version(
            [{"url": "/services/data/v60.0"}, {"url": "/services/data/v61.0"}]
        )
        == "/services/data/v61.0"
    )


@pytest.mark.parametrize("versions", [None, {}, [], [{}], [{"url": ""}]])
def test_latest_api_version_rejects_invalid_payloads(versions: object) -> None:
    with pytest.raises(ActionFailure):
        _latest_api_version(versions)
