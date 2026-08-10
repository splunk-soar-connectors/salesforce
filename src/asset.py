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
from soar_sdk.asset import AssetField, BaseAsset, FieldCategory


class Asset(BaseAsset):
    client_id: str = AssetField(
        description="Salesforce OAuth client identifier, also called the consumer key."
    )
    client_secret: str = AssetField(
        description="Salesforce OAuth client secret, also called the consumer secret.",
        sensitive=True,
    )
    use_client_credentials: bool | None = AssetField(
        description="Use Salesforce Client Credentials OAuth flow."
    )
    domain_url: str | None = AssetField(
        description="Salesforce Current My Domain URL used for Client Credentials flow."
    )
    username: str | None = AssetField(
        description="(Legacy) Username for username-password OAuth flow. Not required for External Client App setup."
    )
    password: str | None = AssetField(
        description="(Legacy) Password with security token appended. Not required for External Client App setup.",
        sensitive=True,
    )
    is_test_environment: bool | None = AssetField(
        description="Use a Salesforce test environment for browser OAuth and legacy username-password flows"
    )
    poll_sobject: str | None = AssetField(
        description="Poll for this Salesforce Object",
        default="Case",
        category=FieldCategory.INGEST,
    )
    poll_view_name: str | None = AssetField(
        description="Poll this List View", category=FieldCategory.INGEST
    )
    first_ingestion_max: float | None = AssetField(
        description="Get this many results on first ingestion",
        default=10.0,
        category=FieldCategory.INGEST,
    )
    cef_name_map: str | None = AssetField(
        description="Mapping of Salesforce to CEF fields (JSON file)",
        category=FieldCategory.INGEST,
    )
    last_view_date: bool | None = AssetField(
        description="Include view date in artifact",
        default=True,
        category=FieldCategory.INGEST,
    )
