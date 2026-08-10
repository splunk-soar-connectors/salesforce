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
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient


class PostChatterParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
    title: str | None = Param(description="Title of the post")
    body: str = Param(description="Body of the post")


class PostChatterActorOutput(PermissiveActionOutput):
    id: str | None = OutputField(
        cef_types=["salesforce object id"], example_values=["005D00000016Qxp"]
    )
    name: str | None = OutputField(example_values=["Jane Doe"])
    type: str | None = OutputField(example_values=["User"])
    url: str | None = None


class PostChatterBodyOutput(PermissiveActionOutput):
    text: str | None = OutputField(
        example_values=["When should we meet for release planning?"]
    )
    messageSegments: list[str] | None = None


class PostChatterParentOutput(PermissiveActionOutput):
    id: str | None = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    name: str | None = None
    type: str | None = None
    url: str | None = None


class PostChatterOutput(PermissiveActionOutput):
    status: str = OutputField(column_name="STATUS", example_values=["success"])
    id: str | None = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["0D51I00000Jw1tnSAB"],
    )
    success: bool | None = OutputField(example_values=[True])
    url: str | None = OutputField(
        example_values=["/services/data/v59.0/chatter/feed-elements/0D51I00000Jw1tnSAB"]
    )
    feedElementType: str | None = OutputField(example_values=["FeedItem"])
    type: str | None = OutputField(example_values=["TextPost"])
    createdDate: str | None = OutputField(example_values=["2017-12-01T21:32:33.000Z"])
    modifiedDate: str | None = OutputField(example_values=["2017-12-01T21:32:33.000Z"])
    relativeCreatedDate: str | None = OutputField(example_values=["Just now"])
    visibility: str | None = OutputField(example_values=["AllUsers"])
    event: bool | None = None
    isDeleteRestricted: bool | None = None
    isSharable: bool | None = None
    actor: PostChatterActorOutput | None = None
    body: PostChatterBodyOutput | None = None
    parent: PostChatterParentOutput | None = None
    capabilities: PermissiveActionOutput | None = None


def post_chatter(
    params: PostChatterParams, soar: SOARClient, asset: Asset
) -> PostChatterOutput:
    result = SalesforceClient(asset).post_chatter(
        params.id, params.body, title=params.title
    )
    soar.set_message("Successfully posted to chatter")
    return PostChatterOutput.model_validate(
        {**result, "status": "success", "success": True}
    )
