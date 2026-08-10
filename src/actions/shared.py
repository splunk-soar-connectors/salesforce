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
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput


class StatusOutput(ActionOutput):
    status: str = OutputField(column_name="STATUS", example_values=["success"])


class CreateSummary(ActionOutput):
    obj_id: str = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListSummary(ActionOutput):
    num_objects: int = OutputField(example_values=[5])
    view_names: list[str] | None = OutputField(
        example_values=[["All", "My Cases", "Today's Cases"]]
    )


class ListObjectsColumnIdValue(PermissiveActionOutput):
    value: str = OutputField(
        column_name="OBJECT ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListTicketsColumnIdValue(PermissiveActionOutput):
    value: str = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListTicketsColumnStringValue(PermissiveActionOutput):
    value: str = OutputField(example_values=[""])


class ListTicketsColumnSubjectValue(PermissiveActionOutput):
    value: str = OutputField(column_name="Subject", example_values=[""])


class ListTicketsColumnStatusValue(PermissiveActionOutput):
    value: str = OutputField(column_name="Status", example_values=["New"])


class ListTicketsColumnPriorityValue(PermissiveActionOutput):
    value: str = OutputField(column_name="Priority", example_values=["High"])


class ListTicketsColumnCaseNumberValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["00001028"])


class ListTicketsColumnContactIdValue(PermissiveActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSWABZ"]
    )


class ListTicketsColumnContactNameValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["Abcd"])


class ListTicketsColumnCreatedDateValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["Thu Nov 30 23:50:55 GMT 2017"])


class ListTicketsColumnLastModifiedDateValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["Fri Dec 01 00:17:47 GMT 2017"])


class ListTicketsColumnOwnerIdValue(PermissiveActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )


class ListTicketsColumnOwnerNameOrAliasValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["testuser"])


class ListTicketsColumnRecordTypeIdValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["0121I000000F7aZQAS"])


class ListTicketsColumnSystemModstampValue(PermissiveActionOutput):
    value: str = OutputField(example_values=["Sat Dec 02 11:18:29 GMT 2017"])


class ListObjectsColumnsOutput(PermissiveActionOutput):
    Id: ListObjectsColumnIdValue


class ListTicketsColumnsOutput(PermissiveActionOutput):
    CaseNumber: ListTicketsColumnCaseNumberValue
    ContactId: ListTicketsColumnContactIdValue
    Contact_Id: ListTicketsColumnContactIdValue
    Contact_Name: ListTicketsColumnContactNameValue
    CreatedDate: ListTicketsColumnCreatedDateValue
    Id: ListTicketsColumnIdValue
    LastModifiedDate: ListTicketsColumnLastModifiedDateValue
    OwnerId: ListTicketsColumnOwnerIdValue
    Owner_Id: ListTicketsColumnOwnerIdValue
    Owner_NameOrAlias: ListTicketsColumnOwnerNameOrAliasValue
    Subject: ListTicketsColumnSubjectValue
    Status: ListTicketsColumnStatusValue
    Priority: ListTicketsColumnPriorityValue
    RecordTypeId: ListTicketsColumnRecordTypeIdValue
    SystemModstamp: ListTicketsColumnSystemModstampValue
