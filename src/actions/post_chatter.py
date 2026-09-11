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
import json

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.params import Param, Params

from ..asset import Asset
from .create_object import CreateObjectParams, create_object


class PostChatterParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
    title: str | None = Param(description="Title of the post")
    body: str = Param(description="Body of the post")


class PostChatterOutput(PermissiveActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0D51I00000Jw1tnSAB"]
    )
    success: bool


class PostChatterSummary(ActionOutput):
    obj_id: str = OutputField(
        cef_types=["salesforce object id"],
        example_values=["0D51I00000Jw1tnSAB"],
        column_name="ID",
    )


def post_chatter(
    params: PostChatterParams, soar: SOARClient, asset: Asset
) -> PostChatterOutput:
    result = create_object(
        CreateObjectParams(
            sobject="FeedItem",
            field_values=json.dumps(
                {
                    "ParentId": params.id,
                    "Title": params.title,
                    "Body": params.body,
                    "Type": "TextPost",
                }
            ),
        ),
        soar,
        asset,
    )
    soar.set_summary(PostChatterSummary(obj_id=result.id))
    soar.set_message("Successfully posted to chatter")
    return PostChatterOutput.model_validate(result.model_dump())
