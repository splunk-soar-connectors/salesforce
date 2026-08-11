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
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Param, Params

from ..asset import Asset


class ListTicketsParams(Params):
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class CasenumberOutput(ActionOutput):
    value: str = OutputField(example_values=["00001028"])


class ContactidOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSWABZ"]
    )


class ContactIdOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSWABZ"]
    )


class ContactNameOutput(ActionOutput):
    value: str = OutputField(example_values=["Abcd"])


class CreateddateOutput(ActionOutput):
    value: str = OutputField(example_values=["Thu Nov 30 23:50:55 GMT 2017"])


class ListTicketsIdOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002Sd2hQAC"]
    )


class LastmodifieddateOutput(ActionOutput):
    value: str = OutputField(example_values=["Fri Dec 01 00:17:47 GMT 2017"])


class OwneridOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )


class OwnerIdOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )


class OwnerNameoraliasOutput(ActionOutput):
    value: str = OutputField(example_values=["testuser"])


class PriorityOutput(ActionOutput):
    value: str = OutputField(example_values=["Medium"])


class RecordtypeidOutput(ActionOutput):
    value: str = OutputField(example_values=["0121I000000F7aZQAS"])


class StatusOutput(ActionOutput):
    value: str = OutputField(example_values=["In-Progress"])


class SubjectOutput(ActionOutput):
    value: str = OutputField(example_values=["Panic"])


class SystemmodstampOutput(ActionOutput):
    value: str = OutputField(example_values=["Sat Dec 02 11:18:29 GMT 2017"])


class ListTicketsColumnsOutput(ActionOutput):
    CaseNumber: CasenumberOutput
    ContactId: ContactidOutput
    Contact_Id: ContactIdOutput
    Contact_Name: ContactNameOutput
    CreatedDate: CreateddateOutput
    Id: ListTicketsIdOutput
    LastModifiedDate: LastmodifieddateOutput
    OwnerId: OwneridOutput
    Owner_Id: OwnerIdOutput
    Owner_NameOrAlias: OwnerNameoraliasOutput
    Priority: PriorityOutput
    RecordTypeId: RecordtypeidOutput
    Status: StatusOutput
    Subject: SubjectOutput
    SystemModstamp: SystemmodstampOutput


class ListTicketsOutput(ActionOutput):
    columns: ListTicketsColumnsOutput


def list_tickets(
    params: ListTicketsParams, soar: SOARClient, asset: Asset
) -> ListTicketsOutput:
    raise NotImplementedError()
