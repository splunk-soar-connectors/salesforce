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
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import CreateSummary, StatusOutput


class UpdateTicketParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
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
    status: str | None = Param(
        description="Status", value_list=["New", "Working", "Escalated", "Closed"]
    )
    field_values: str | None = Param(
        description="JSON Object of Key-Value pairs to update"
    )


def update_ticket(
    params: UpdateTicketParams, soar: SOARClient, asset: Asset
) -> StatusOutput:
    fields: dict = {}
    if params.parent_case_id:
        fields["ParentId"] = params.parent_case_id
    if params.subject:
        fields["Subject"] = params.subject
    if params.priority:
        fields["Priority"] = params.priority
    if params.description:
        fields["Description"] = params.description
    if params.status:
        fields["Status"] = params.status
    if params.field_values:
        try:
            extra = json.loads(params.field_values)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"field_values must be valid JSON: {e}") from e
        fields.update(extra)
    if not fields:
        raise ActionFailure("Provide at least one field to update.")
    SalesforceClient(asset).update("Case", params.id, fields)
    soar.set_summary(CreateSummary(obj_id=params.id))
    soar.set_message("Successfully updated the Case")
    return StatusOutput(status="success")
