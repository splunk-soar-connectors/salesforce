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
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from .create_object import (
    CreateObjectParams,
    create_object,
)


CASE_FIELD_MAP = {
    "parent_case_id": "ParentId",
    "subject": "Subject",
    "priority": "Priority",
    "description": "Description",
}


class CreateTicketParams(Params):
    parent_case_id: str | None = Param(
        description="Object ID of Parent Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
    subject: str | None = Param(description="Subject")
    priority: str | None = Param(
        description="Priority", value_list=["High", "Medium", "Low"]
    )
    description: str | None = Param(description="Description")
    field_values: str | None = Param(
        description="JSON Object of Key-Value pairs to update"
    )


class CreateTicketOutput(PermissiveActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


def create_ticket(
    params: CreateTicketParams, soar: SOARClient, asset: Asset
) -> CreateTicketOutput:
    if params.field_values:
        try:
            field_values = json.loads(params.field_values)
        except (TypeError, ValueError) as error:
            raise ActionFailure(f"Error reading 'field_values': {error}") from error
    else:
        field_values = {}

    mapped_values = {
        salesforce_field: value
        for param_name, salesforce_field in CASE_FIELD_MAP.items()
        if (value := getattr(params, param_name)) is not None
    }
    if mapped_values:
        if not isinstance(field_values, dict):
            raise ActionFailure("Error reading 'field_values': expected a JSON object")
        field_values.update(mapped_values)

    result = create_object(
        CreateObjectParams(sobject="Case", field_values=json.dumps(field_values)),
        soar,
        asset,
    )
    return CreateTicketOutput.model_validate(result.model_dump())
