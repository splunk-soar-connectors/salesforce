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


class GetTicketParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )


class AttributesOutput(ActionOutput):
    type: str = OutputField(example_values=["Case"])
    url: str = OutputField(
        example_values=["/services/data/v41.0/sobjects/Case/5001I000002SfMMQA0"]
    )


class GetTicketOutput(ActionOutput):
    AccountId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0013t00001ZyVVTAB4"]
    )
    AssetId: str
    CaseNumber: str = OutputField(example_values=["00001030"])
    Case_Open_minutes__c: float = OutputField(example_values=[4218])
    ClosedDate: str = OutputField(example_values=["2019-06-25T18:59:51.000+0000"])
    Closed_Time_Days__c: str
    ContactEmail: str = OutputField(example_values=["test@example.com"])
    ContactFax: str = OutputField(example_values=["(1) 234 567"])
    ContactId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSWABZ"]
    )
    ContactMobile: str = OutputField(example_values=["(1) 222 333"])
    ContactPhone: str = OutputField(example_values=["(1) 33 444"])
    CreatedById: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )
    CreatedDate: str = OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    Customer_Impacting__c: str
    Date_Reviewed__c: str
    Days_Open__c: float = OutputField(example_values=[3])
    Description: str = OutputField(example_values=["Case Description"])
    Discovery_Method__c: str
    Discovery_Time_Hours__c: str
    EngineeringReqNumber__c: str = OutputField(example_values=["765810"])
    Executive_Summary__c: str
    Id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    Impact_Summary__c: str
    Impacted_Environment__c: str
    Incident_Category__c: str
    Incident_Date__c: str
    Incident_Root_Cause__c: str
    Incident_Sensitivity__c: str
    Incident_Severity__c: str
    Incident_Type__c: str
    Investigation_Category__c: str
    Investigation_Date__c: str
    Investigation_Summary__c: str
    Investigation_Type__c: str
    IsClosed: bool
    IsDeleted: bool
    IsEscalated: bool
    LastModifiedById: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )
    LastModifiedDate: str = OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    LastReferencedDate: str = OutputField(
        example_values=["2017-12-01T21:33:05.000+0000"]
    )
    LastViewedDate: str = OutputField(example_values=["2017-12-01T21:33:05.000+0000"])
    Origin: str
    OwnerId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )
    ParentId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0061I000000PRsCABC"]
    )
    PotentialLiability__c: str = OutputField(example_values=["No"])
    Priority: str = OutputField(example_values=["High"])
    Product__c: str = OutputField(example_values=["GC5555"])
    Reason: str = OutputField(example_values=["Test Complexity"])
    RecordTypeId: str = OutputField(example_values=["0121I000000F7aZQAS"])
    Resolution_Date__c: str
    Resolution_Time_Hours__c: str
    Response_Time_Hours__c: str
    Response_Time_Minutes__c: float = OutputField(example_values=[4218])
    SITrack_Response_Task__c: str
    SITracker_Handoff_Notes__c: str
    SITracker_Include_in_Handoff__c: bool
    SLAViolation__c: str
    Status: str = OutputField(example_values=["New"])
    Subject: str = OutputField(example_values=["Case Subject"])
    SuppliedCompany: str
    SuppliedEmail: str
    SuppliedName: str
    SuppliedPhone: str
    SystemModstamp: str = OutputField(example_values=["2017-12-02T11:18:29.000+0000"])
    Type: str = OutputField(example_values=["Electrical"])
    attributes: AttributesOutput


def get_ticket(
    params: GetTicketParams, soar: SOARClient, asset: Asset
) -> GetTicketOutput:
    raise NotImplementedError()
