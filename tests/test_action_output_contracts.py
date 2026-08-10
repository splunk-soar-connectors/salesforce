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
from src.actions.get_object import GetObjectOutput
from src.actions.get_ticket import GetTicketOutput
from src.actions.post_chatter import PostChatterOutput
from src.actions.shared import ListTicketsColumnsOutput


def _schema_by_path(output_type, parent_datapath="action_result.data.*"):
    return {
        field["data_path"]: field
        for field in output_type._to_json_schema(parent_datapath)
    }


def test_salesforce_extras_are_retained():
    output = GetObjectOutput.model_validate({"Id": "001", "Custom__c": 42})

    assert output.model_dump() == {"Id": "001", "Custom__c": 42}


def test_legacy_datapaths_and_widget_columns_are_published():
    get_ticket_schema = _schema_by_path(GetTicketOutput)
    list_tickets_schema = _schema_by_path(
        ListTicketsColumnsOutput, "action_result.data.*.columns"
    )
    post_chatter_schema = _schema_by_path(PostChatterOutput)

    assert "action_result.data.*.attributes.type" in get_ticket_schema
    assert "action_result.data.*.attributes.url" in get_ticket_schema

    expected_ticket_columns = {
        "CaseNumber",
        "ContactId",
        "Contact_Id",
        "Contact_Name",
        "CreatedDate",
        "Id",
        "LastModifiedDate",
        "OwnerId",
        "Owner_Id",
        "Owner_NameOrAlias",
        "Priority",
        "RecordTypeId",
        "Status",
        "Subject",
        "SystemModstamp",
    }
    assert {
        path.removeprefix("action_result.data.*.columns.").removesuffix(".value")
        for path in list_tickets_schema
    } == expected_ticket_columns
    assert [
        field["column_name"]
        for field in get_ticket_schema.values()
        if "column_name" in field
    ] == ["SUBJECT", "DESCRIPTION", "LAST MODIFIED", "CREATED BY ID"]
    assert [
        field["column_name"]
        for field in post_chatter_schema.values()
        if "column_name" in field
    ] == ["STATUS", "ID"]
