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
from src.actions.get_ticket import AttributesOutput, GetTicketOutput


def test_get_ticket_accepts_nullable_salesforce_case_fields():
    output = GetTicketOutput.model_validate(
        {
            "Id": "5001I000002SfMMQA0",
            "AssetId": None,
            "AccountId": None,
            "ContactId": None,
            "Subject": None,
            "Description": None,
            "ClosedDate": None,
            "LastViewedDate": None,
            "LastReferencedDate": None,
            "ParentId": None,
            "RecordTypeId": None,
            "Type": None,
            "IsClosed": False,
            "IsDeleted": False,
            "IsEscalated": False,
            "Origin": "Web",
            "custom_provider_field__c": "retained",
            "attributes": {
                "type": "Case",
                "url": "/services/data/v66.0/sobjects/Case/5001I000002SfMMQA0",
            },
        }
    )

    assert isinstance(output.attributes, AttributesOutput)
    assert output.AssetId is None
    assert output.model_dump()["custom_provider_field__c"] == "retained"
