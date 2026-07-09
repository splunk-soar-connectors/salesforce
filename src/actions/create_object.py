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
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import CreateSummary


class CreateObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    field_values: str = Param(description="JSON Object of Key-Value pairs to update")


class CreateObjectOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


def create_object(
    params: CreateObjectParams, soar: SOARClient, asset: Asset
) -> CreateObjectOutput:
    try:
        fields = json.loads(params.field_values)
    except (json.JSONDecodeError, TypeError) as e:
        raise ActionFailure(f"field_values must be valid JSON: {e}") from e
    client = SalesforceClient(asset)
    result = client.create(params.sobject, fields)
    obj_id = result["id"]
    soar.set_summary(CreateSummary(obj_id=obj_id))
    soar.set_message(f"Successfully created a new {params.sobject}")
    return CreateObjectOutput(id=obj_id, success=result.get("success", True))
