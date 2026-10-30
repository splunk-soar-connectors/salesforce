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
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.params import Param, Params

from ..asset import Asset
from .list_objects import ListObjectsParams, list_objects


class ListTicketsParams(Params):
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class CasenumberOutput(ActionOutput):
    value: str | None = OutputField(example_values=["00001028"])


class ContactidOutput(ActionOutput):
    value: str | None = OutputField(
        cef_types=["salesforce object id"],
        example_values=["0033t000035qrSWABZ"],
    )


class ContactIdOutput(ActionOutput):
    value: str | None = OutputField(
        cef_types=["salesforce object id"],
        example_values=["0033t000035qrSWABZ"],
    )


class ContactNameOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Abcd"])


class CreateddateOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Thu Nov 30 23:50:55 GMT 2017"])


class ListTicketsIdOutput(ActionOutput):
    value: str | None = OutputField(
        cef_types=["salesforce object id"],
        example_values=["5001I000002Sd2hQAC"],
        column_name="ID",
    )


class LastmodifieddateOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Fri Dec 01 00:17:47 GMT 2017"])


class OwneridOutput(ActionOutput):
    value: str | None = OutputField(
        cef_types=["salesforce object id"],
        example_values=["0051I000000PRsCQAW"],
    )


class OwnerIdOutput(ActionOutput):
    value: str | None = OutputField(
        cef_types=["salesforce object id"],
        example_values=["0051I000000PRsCQAW"],
    )


class OwnerNameoraliasOutput(ActionOutput):
    value: str | None = OutputField(example_values=["testuser"])


class PriorityOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Medium"], column_name="Priority")


class RecordtypeidOutput(ActionOutput):
    value: str | None = OutputField(example_values=["0121I000000F7aZQAS"])


class StatusOutput(ActionOutput):
    value: str | None = OutputField(
        example_values=["In-Progress"], column_name="Status"
    )


class SubjectOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Panic"], column_name="Subject")


class SystemmodstampOutput(ActionOutput):
    value: str | None = OutputField(example_values=["Sat Dec 02 11:18:29 GMT 2017"])


class ListTicketsColumnsOutput(PermissiveActionOutput):
    Id: ListTicketsIdOutput | None = None
    Subject: SubjectOutput | None = None
    Status: StatusOutput | None = None
    Priority: PriorityOutput | None = None
    CaseNumber: CasenumberOutput | None = None
    ContactId: ContactidOutput | None = None
    Contact_Id: ContactIdOutput | None = None
    Contact_Name: ContactNameOutput | None = None
    CreatedDate: CreateddateOutput | None = None
    LastModifiedDate: LastmodifieddateOutput | None = None
    OwnerId: OwneridOutput | None = None
    Owner_Id: OwnerIdOutput | None = None
    Owner_NameOrAlias: OwnerNameoraliasOutput | None = None
    RecordTypeId: RecordtypeidOutput | None = None
    SystemModstamp: SystemmodstampOutput | None = None


class ListTicketsOutput(PermissiveActionOutput):
    columns: ListTicketsColumnsOutput | None = None


def list_tickets(
    params: ListTicketsParams, soar: SOARClient, asset: Asset
) -> list[ListTicketsOutput]:
    records = list_objects(
        ListObjectsParams(
            sobject="Case",
            view_name=params.view_name,
            limit=params.limit,
            offset=params.offset,
        ),
        soar,
        asset,
    )
    return [ListTicketsOutput.model_validate(record.model_dump()) for record in records]
