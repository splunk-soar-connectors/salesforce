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
from soar_sdk.action_results import OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import CreateSummary, StatusOutput


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


class CreateTicketOutput(StatusOutput):
    id: str = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )
    success: bool
    errors: list[str] | None = None


def create_ticket(
    params: CreateTicketParams, soar: SOARClient, asset: Asset
) -> CreateTicketOutput:
    fields: dict = {}
    if params.parent_case_id:
        fields["ParentId"] = params.parent_case_id
    if params.subject:
        fields["Subject"] = params.subject
    if params.priority:
        fields["Priority"] = params.priority
    if params.description:
        fields["Description"] = params.description
    if params.field_values:
        try:
            extra = json.loads(params.field_values)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"field_values must be valid JSON: {e}") from e
        fields.update(extra)
    client = SalesforceClient(asset)
    result = client.create("Case", fields)
    obj_id = result["id"]
    soar.set_summary(CreateSummary(obj_id=obj_id))
    soar.set_message("Successfully created a new Case")
    return CreateTicketOutput(
        status="success",
        id=obj_id,
        success=result.get("success", True),
        errors=result.get("errors"),
    )
