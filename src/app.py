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
from collections.abc import Iterator
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Param, Params, OnPollParams
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.asset import AssetField, BaseAsset, FieldCategory
from soar_sdk.logging import getLogger
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact

logger = getLogger()


class Asset(BaseAsset):
    client_id: str = AssetField(
        description="Salesforce OAuth client identifier, also called the consumer key."
    )
    client_secret: str = AssetField(
        description="Salesforce OAuth client secret, also called the consumer secret.",
        sensitive=True,
    )
    use_client_credentials: bool | None = AssetField(
        description="Use Salesforce Client Credentials OAuth flow."
    )
    domain_url: str | None = AssetField(
        description="Salesforce Current My Domain URL used for Client Credentials flow."
    )
    username: str | None = AssetField(
        description="(Legacy) Username for username-password OAuth flow. Not required for External Client App setup."
    )
    password: str | None = AssetField(
        description="(Legacy) Password with security token appended. Not required for External Client App setup.",
        sensitive=True,
    )
    is_test_environment: bool | None = AssetField(
        description="Use a Salesforce test environment for browser OAuth and legacy username-password flows"
    )
    poll_sobject: str | None = AssetField(
        description="Poll for this Salesforce Object",
        default="Case",
        category=FieldCategory.INGEST,
    )
    poll_view_name: str | None = AssetField(
        description="Poll this List View", category=FieldCategory.INGEST
    )
    first_ingestion_max: float | None = AssetField(
        description="Get this many results on first ingestion",
        default=10.0,
        category=FieldCategory.INGEST,
    )
    cef_name_map: str | None = AssetField(
        description="Mapping of Salesforce to CEF fields (JSON file)",
        category=FieldCategory.INGEST,
    )
    last_view_date: bool | None = AssetField(
        description="Include view date in artifact",
        default=True,
        category=FieldCategory.INGEST,
    )


app = App(
    name="Salesforce",
    app_type="ticketing",
    logo="logo_salesforce.svg",
    logo_dark="logo_salesforce_dark.svg",
    product_vendor="Salesforce",
    product_name="Salesforce",
    publisher="Splunk",
    appid="6c1316b0-88a7-4864-b684-3170f6c455be",
    fips_compliant=True,
    encrypt_cache_state=True,
    encrypt_ingest_state=True,
    asset_cls=Asset,
)


@app.on_poll()
def on_poll(
    soar: SOARClient, asset: Asset, params: OnPollParams
) -> Iterator[Container | Artifact]:
    raise NotImplementedError()


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    raise NotImplementedError()


class RunQueryParams(Params):
    query: str = Param(description="SOQL Query")
    endpoint: str = Param(
        description="Which Query endpoint to use",
        default="query",
        value_list=["query", "queryAll"],
    )


class RunQueryOutput(ActionOutput):
    records: list[str]


@app.action(  # type: ignore[arg-type]
    description="Run a query using the Salesforce Object Query Language (SOQL)",
    action_type="investigate",
    verbose="To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>.",
)
def run_query(params: RunQueryParams, soar: SOARClient, asset: Asset) -> RunQueryOutput:
    raise NotImplementedError()


class CreateObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    field_values: str = Param(description="JSON Object of Key-Value pairs to update")


class CreateObjectOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


@app.action(  # type: ignore[arg-type]
    description="Create a new Salesforce object", action_type="generic", read_only=False
)
def create_object(
    params: CreateObjectParams, soar: SOARClient, asset: Asset
) -> CreateObjectOutput:
    raise NotImplementedError()


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


class CreateTicketOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


@app.action(  # type: ignore[arg-type]
    description="Create a new Case", action_type="generic", read_only=False
)
def create_ticket(
    params: CreateTicketParams, soar: SOARClient, asset: Asset
) -> CreateTicketOutput:
    raise NotImplementedError()


class DeleteObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    id: str = Param(
        description="Salesforce Object ID",
        primary=True,
        cef_types=["salesforce object id"],
    )


@app.action(  # type: ignore[arg-type]
    description="Delete an object", action_type="generic", read_only=False
)
def delete_object(
    params: DeleteObjectParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    raise NotImplementedError()


class DeleteTicketParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )


@app.action(  # type: ignore[arg-type]
    description="Delete a Case", action_type="generic", read_only=False
)
def delete_ticket(
    params: DeleteTicketParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    raise NotImplementedError()


class UpdateObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    id: str = Param(
        description="Salesforce Object ID",
        primary=True,
        cef_types=["salesforce object id"],
    )
    field_values: str | None = Param(
        description="JSON Object of Key-Value pairs to update"
    )


@app.action(  # type: ignore[arg-type]
    description="Update an object", action_type="generic", read_only=False
)
def update_object(
    params: UpdateObjectParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    raise NotImplementedError()


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


@app.action(  # type: ignore[arg-type]
    description="Update a Case", action_type="generic", read_only=False
)
def update_ticket(
    params: UpdateTicketParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    raise NotImplementedError()


class ListObjectsParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class ListObjectsIdOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSYAAY"]
    )


class ListObjectsColumnsOutput(ActionOutput):
    Id: ListObjectsIdOutput


class ListObjectsOutput(ActionOutput):
    columns: ListObjectsColumnsOutput


@app.action(  # type: ignore[arg-type]
    description="Get a list of objects",
    action_type="investigate",
    verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary. Also, this action will only work if the specified object has a list view. If it does not, you could use the <b>run query</b> action instead.",
)
def list_objects(
    params: ListObjectsParams, soar: SOARClient, asset: Asset
) -> ListObjectsOutput:
    raise NotImplementedError()


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


@app.action(  # type: ignore[arg-type]
    description="Get a list of Cases",
    action_type="investigate",
    verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary.",
)
def list_tickets(
    params: ListTicketsParams, soar: SOARClient, asset: Asset
) -> ListTicketsOutput:
    raise NotImplementedError()


class GetObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    id: str = Param(
        description="Salesforce Object ID",
        primary=True,
        cef_types=["salesforce object id"],
    )


class GetObjectOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )


@app.action(  # type: ignore[arg-type]
    description="Get info about a Salesforce object",
    action_type="investigate",
    verbose="If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
)
def get_object(
    params: GetObjectParams, soar: SOARClient, asset: Asset
) -> GetObjectOutput:
    raise NotImplementedError()


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


@app.action(  # type: ignore[arg-type]
    description="Get info about a Case",
    action_type="investigate",
    verbose="If you have custom fields added to a Case, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
)
def get_ticket(
    params: GetTicketParams, soar: SOARClient, asset: Asset
) -> GetTicketOutput:
    raise NotImplementedError()


class PostChatterParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
    title: str | None = Param(description="Title of the post")
    body: str = Param(description="Body of the post")


class PostChatterOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0D51I00000Jw1tnSAB"]
    )
    success: bool


@app.action(  # type: ignore[arg-type]
    description="Post on the Chatter feed for a specified case",
    action_type="generic",
    read_only=False,
)
def post_chatter(
    params: PostChatterParams, soar: SOARClient, asset: Asset
) -> PostChatterOutput:
    raise NotImplementedError()


if __name__ == "__main__":
    app.cli()
