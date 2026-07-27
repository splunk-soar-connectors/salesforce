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
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient


class GetTicketParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )


class GetTicketOutput(PermissiveActionOutput):
    # Always-present fields on an existing Case
    Id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    CaseNumber: str = OutputField(example_values=["00001030"])
    OwnerId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )
    CreatedDate: str = OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    SystemModstamp: str = OutputField(example_values=["2017-12-02T11:18:29.000+0000"])
    IsClosed: bool = False
    IsDeleted: bool = False
    IsEscalated: bool = False
    # Optional standard fields — column_name fields declared first to control column order
    Subject: str | None = OutputField(column_name="SUBJECT")
    Description: str | None = OutputField(column_name="DESCRIPTION")
    LastModifiedDate: str = OutputField(
        column_name="LAST MODIFIED", example_values=["2017-12-01T21:32:33.000+0000"]
    )
    CreatedById: str | None = OutputField(
        column_name="CREATED BY ID", cef_types=["salesforce object id"]
    )
    AccountId: str | None = None
    AssetId: str | None = None
    Case_Open_minutes__c: float | None = None
    ClosedDate: str | None = None
    Closed_Time_Days__c: str | None = None
    ContactEmail: str | None = None
    ContactFax: str | None = None
    ContactId: str | None = None
    ContactMobile: str | None = None
    ContactPhone: str | None = None
    Customer_Impacting__c: str | None = None
    Date_Reviewed__c: str | None = None
    Days_Open__c: float | None = None
    Discovery_Method__c: str | None = None
    Discovery_Time_Hours__c: str | None = None
    EngineeringReqNumber__c: str | None = None
    Executive_Summary__c: str | None = None
    Impact_Summary__c: str | None = None
    Impacted_Environment__c: str | None = None
    Incident_Category__c: str | None = None
    Incident_Date__c: str | None = None
    Incident_Root_Cause__c: str | None = None
    Incident_Sensitivity__c: str | None = None
    Incident_Severity__c: str | None = None
    Incident_Type__c: str | None = None
    Investigation_Category__c: str | None = None
    Investigation_Date__c: str | None = None
    Investigation_Summary__c: str | None = None
    Investigation_Type__c: str | None = None
    LastModifiedById: str | None = None
    LastReferencedDate: str | None = None
    LastViewedDate: str | None = None
    Origin: str | None = None
    ParentId: str | None = None
    PotentialLiability__c: str | None = None
    Priority: str | None = None
    Product__c: str | None = None
    Reason: str | None = None
    RecordTypeId: str | None = None
    Resolution_Date__c: str | None = None
    Resolution_Time_Hours__c: str | None = None
    Response_Time_Hours__c: str | None = None
    Response_Time_Minutes__c: float | None = None
    SITrack_Response_Task__c: str | None = None
    SITracker_Handoff_Notes__c: str | None = None
    SITracker_Include_in_Handoff__c: bool | None = None
    SLAViolation__c: str | None = None
    Status: str | None = None
    SuppliedCompany: str | None = None
    SuppliedEmail: str | None = None
    SuppliedName: str | None = None
    SuppliedPhone: str | None = None
    Type: str | None = None


def get_ticket(
    params: GetTicketParams, soar: SOARClient, asset: Asset
) -> GetTicketOutput:
    record = SalesforceClient(asset).get("Case", params.id)
    soar.set_message("Successfully retrieved Case")
    return GetTicketOutput.model_validate(record)
