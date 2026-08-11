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
from typing import Annotated

from pydantic import ConfigDict, model_serializer
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Param, Params

from ..asset import Asset
from .get_object import GetObjectParams, get_object


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
    model_config = ConfigDict(extra="allow")

    @model_serializer
    def serialize_provider_fields(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.model_fields_set}

    AccountId: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0013t00001ZyVVTAB4"]
        ),
    ] = None
    AssetId: str | None = None
    CaseNumber: Annotated[str | None, OutputField(example_values=["00001030"])] = None
    Case_Open_minutes__c: Annotated[
        float | None, OutputField(example_values=[4218])
    ] = None
    ClosedDate: Annotated[
        str | None, OutputField(example_values=["2019-06-25T18:59:51.000+0000"])
    ] = None
    Closed_Time_Days__c: str | None = None
    ContactEmail: Annotated[
        str | None, OutputField(example_values=["test@example.com"])
    ] = None
    ContactFax: Annotated[str | None, OutputField(example_values=["(1) 234 567"])] = (
        None
    )
    ContactId: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0033t000035qrSWABZ"]
        ),
    ] = None
    ContactMobile: Annotated[
        str | None, OutputField(example_values=["(1) 222 333"])
    ] = None
    ContactPhone: Annotated[str | None, OutputField(example_values=["(1) 33 444"])] = (
        None
    )
    CreatedById: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
        ),
    ] = None
    CreatedDate: Annotated[
        str | None, OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    ] = None
    Customer_Impacting__c: str | None = None
    Date_Reviewed__c: str | None = None
    Days_Open__c: Annotated[float | None, OutputField(example_values=[3])] = None
    Description: Annotated[
        str | None, OutputField(example_values=["Case Description"])
    ] = None
    Discovery_Method__c: str | None = None
    Discovery_Time_Hours__c: str | None = None
    EngineeringReqNumber__c: Annotated[
        str | None, OutputField(example_values=["765810"])
    ] = None
    Executive_Summary__c: str | None = None
    Id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
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
    IsClosed: bool | None = None
    IsDeleted: bool | None = None
    IsEscalated: bool | None = None
    LastModifiedById: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
        ),
    ] = None
    LastModifiedDate: Annotated[
        str | None, OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    ] = None
    LastReferencedDate: Annotated[
        str | None, OutputField(example_values=["2017-12-01T21:33:05.000+0000"])
    ] = None
    LastViewedDate: Annotated[
        str | None, OutputField(example_values=["2017-12-01T21:33:05.000+0000"])
    ] = None
    Origin: str | None = None
    OwnerId: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
        ),
    ] = None
    ParentId: Annotated[
        str | None,
        OutputField(
            cef_types=["salesforce object id"], example_values=["0061I000000PRsCABC"]
        ),
    ] = None
    PotentialLiability__c: Annotated[str | None, OutputField(example_values=["No"])] = (
        None
    )
    Priority: Annotated[str | None, OutputField(example_values=["High"])] = None
    Product__c: Annotated[str | None, OutputField(example_values=["GC5555"])] = None
    Reason: Annotated[str | None, OutputField(example_values=["Test Complexity"])] = (
        None
    )
    RecordTypeId: Annotated[
        str | None, OutputField(example_values=["0121I000000F7aZQAS"])
    ] = None
    Resolution_Date__c: str | None = None
    Resolution_Time_Hours__c: str | None = None
    Response_Time_Hours__c: str | None = None
    Response_Time_Minutes__c: Annotated[
        float | None, OutputField(example_values=[4218])
    ] = None
    SITrack_Response_Task__c: str | None = None
    SITracker_Handoff_Notes__c: str | None = None
    SITracker_Include_in_Handoff__c: bool | None = None
    SLAViolation__c: str | None = None
    Status: Annotated[str | None, OutputField(example_values=["New"])] = None
    Subject: Annotated[str | None, OutputField(example_values=["Case Subject"])] = None
    SuppliedCompany: str | None = None
    SuppliedEmail: str | None = None
    SuppliedName: str | None = None
    SuppliedPhone: str | None = None
    SystemModstamp: Annotated[
        str | None, OutputField(example_values=["2017-12-02T11:18:29.000+0000"])
    ] = None
    Type: Annotated[str | None, OutputField(example_values=["Electrical"])] = None
    attributes: AttributesOutput


def get_ticket(
    params: GetTicketParams, soar: SOARClient, asset: Asset
) -> GetTicketOutput:
    record = get_object(
        GetObjectParams(sobject="Case", id=params.id),
        soar,
        asset,
    )
    return GetTicketOutput.model_validate(record.model_dump())
