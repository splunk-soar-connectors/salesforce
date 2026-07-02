import base64
import hashlib
import secrets
import time
from typing import Union
from collections.abc import Iterator
from urllib.parse import urlencode

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.asset import BaseAsset, AssetField, FieldCategory
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact
from soar_sdk.params import Param, Params, OnPollParams, OnESPollParams
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

logger = getLogger()

SALESFORCE_PKCE_VERIFIER_BYTES = 96
SALESFORCE_DEFAULT_TIMEOUT = 30

URL_GET_CODE = "https://login.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN = "https://login.salesforce.com/services/oauth2/token"
URL_GET_CODE_TEST = "https://test.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN_TEST = "https://test.salesforce.com/services/oauth2/token"

class Asset(BaseAsset):
    client_id: str = AssetField(description='Salesforce OAuth client identifier, also called the consumer key.', category=FieldCategory.CONNECTIVITY)
    client_secret: str = AssetField(description='Salesforce OAuth client secret, also called the consumer secret.', sensitive=True, category=FieldCategory.CONNECTIVITY)
    use_client_credentials: bool | None = AssetField(description='Use Salesforce Client Credentials OAuth flow.', default=False, category=FieldCategory.CONNECTIVITY)
    domain_url: str | None = AssetField(description='Salesforce Current My Domain URL used for Client Credentials flow.', default=None, required=False, category=FieldCategory.CONNECTIVITY)
    username: str | None = AssetField(description='(Legacy) Username for username-password OAuth flow. Not required for External Client App setup.', default=None, required=False, category=FieldCategory.CONNECTIVITY)
    password: str | None = AssetField(description='(Legacy) Password with security token appended. Not required for External Client App setup.', sensitive=True, default=None, required=False, category=FieldCategory.CONNECTIVITY)
    is_test_environment: bool | None = AssetField(description='Use a Salesforce test environment for browser OAuth and legacy username-password flows', default=False, category=FieldCategory.CONNECTIVITY)
    poll_sobject: str | None = AssetField(description='Poll for this Salesforce Object', default='Case', category=FieldCategory.INGEST)
    poll_view_name: str | None = AssetField(description='Poll this List View', default=None, required=False, category=FieldCategory.INGEST)
    first_ingestion_max: float | None = AssetField(description='Get this many results on first ingestion', default=10.0, category=FieldCategory.INGEST)
    cef_name_map: str | None = AssetField(description='Mapping of Salesforce to CEF fields (JSON file)', default=None, required=False, is_file=True, category=FieldCategory.INGEST)
    last_view_date: bool | None = AssetField(description='Include view date in artifact', default=True, category=FieldCategory.INGEST)
app = App(
    name='salesforce',
    app_type='ticketing',
    logo='logo_salesforce.svg',
    logo_dark='logo_salesforce_dark.svg',
    product_vendor='Salesforce',
    product_name='Salesforce',
    publisher='Splunk',
    appid='6c1316b0-88a7-4864-b684-3170f6c455be',
    fips_compliant=True,
    asset_cls=Asset,
).enable_webhooks(default_requires_auth=False)


@app.webhook("/redirect", allowed_methods=["GET"])
def handle_redirect(request: WebhookRequest) -> WebhookResponse:
    """Bounces the browser to the Salesforce authorization URL stored in auth_state."""
    asset: Asset = request.asset
    url = asset.auth_state.get("url")
    if not url:
        return WebhookResponse.text_response("ERROR: No authorization URL found. Re-run test connectivity.", status_code=400)
    return WebhookResponse(status_code=302, content="", headers=[("Location", url)])


@app.webhook("/start_oauth", allowed_methods=["GET"])
def handle_start_oauth(request: WebhookRequest) -> WebhookResponse:
    """Receives the OAuth callback from Salesforce, exchanges the code for a refresh token."""
    asset: Asset = request.asset
    auth_state = asset.auth_state

    code = (request.query.get("code") or [""])[0]
    if not code:
        error = (request.query.get("error_description") or request.query.get("error") or ["Unknown error"])[0]
        auth_state["error"] = True
        return WebhookResponse.text_response(f"Authentication failed: {error}", status_code=401)

    url_get_token = auth_state.get("url_get_token")
    if not url_get_token:
        auth_state["error"] = True
        return WebhookResponse.text_response("ERROR: State missing token URL. Re-run test connectivity.", status_code=400)

    token_body = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": auth_state["client_id"],
        "redirect_uri": auth_state["redirect_uri"],
        "client_secret": auth_state["client_secret"],
        "code_verifier": auth_state["code_verifier"],
    }

    try:
        r = httpx.post(
            url_get_token,
            data=token_body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = r.json()
    except Exception as e:
        auth_state["error"] = True
        return WebhookResponse.text_response(f"Error retrieving OAuth token: {e}", status_code=401)

    sf_error = resp_json.get("error_description") or resp_json.get("error")
    if sf_error:
        auth_state["error"] = True
        return WebhookResponse.text_response(f"Salesforce token exchange failed: {sf_error}", status_code=401)

    refresh_token = resp_json.get("refresh_token")
    if not refresh_token:
        auth_state["error"] = True
        return WebhookResponse.text_response("Unable to retrieve refresh token. Check OAuth scopes include refresh_token.", status_code=401)

    auth_state["refresh_token"] = refresh_token
    auth_state.pop("url", None)
    auth_state.pop("url_get_token", None)
    auth_state.pop("client_id", None)
    auth_state.pop("client_secret", None)
    auth_state.pop("redirect_uri", None)
    auth_state.pop("code_verifier", None)
    auth_state.pop("error", None)

    return WebhookResponse.text_response("You can now close this page.")


@app.on_poll()
def on_poll(soar: SOARClient, asset: Asset, params: OnPollParams) -> Iterator[Union[Container, Artifact]]:
    raise NotImplementedError()


@app.test_connectivity()
def test_connectivity(soar: SOARClient, asset: Asset) -> None:
    """Validate connection using the configured credentials"""
    if asset.use_client_credentials:
        _test_connectivity_client_credentials(soar, asset)
    elif asset.username and asset.password:
        _test_connectivity_username_password(soar, asset)
    else:
        _test_connectivity_oauth(soar, asset)

    # Verify API access by fetching available versions
    logger.info("Obtaining Salesforce API version")
    try:
        resp = httpx.get(
            _get_salesforce_instance_url(asset) + "/services/data/",
            headers={"Authorization": f"Bearer {_get_access_token(asset)}"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp.raise_for_status()
        versions = resp.json()
        latest = versions[-1]["url"]
        asset.cache_state["latest_version"] = latest
        logger.info(f"Latest Salesforce API version: {latest}")
    except Exception as e:
        raise ActionFailure(f"Connected but failed to fetch API version: {e}") from e


def _test_connectivity_oauth(soar: SOARClient, asset: Asset) -> None:
    """Browser-based OAuth with PKCE flow."""
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(SALESFORCE_PKCE_VERIFIER_BYTES)
    ).rstrip(b"=").decode()
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode()

    redirect_uri = app.get_webhook_url("start_oauth")

    if asset.is_test_environment:
        url_get_code = URL_GET_CODE_TEST
        url_get_token = URL_GET_TOKEN_TEST
    else:
        url_get_code = URL_GET_CODE
        url_get_token = URL_GET_TOKEN

    auth_params = {
        "response_type": "code",
        "client_id": asset.client_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    full_auth_url = f"{url_get_code}?{urlencode(auth_params)}"

    # Write PKCE state so webhooks can pick it up; keep secrets plaintext since
    # AssetState encrypts the whole partition at rest.
    auth_state = asset.auth_state
    auth_state.put_all({
        "url": full_auth_url,
        "url_get_token": url_get_token,
        "client_id": asset.client_id,
        "client_secret": asset.client_secret,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    })

    redirect_url = app.get_webhook_url("redirect")
    logger.info(f"To continue, open this link in a new tab: {redirect_url}")

    # Poll until the start_oauth webhook writes the refresh_token (up to 5 min)
    for _ in range(60):
        time.sleep(5)
        state = auth_state.get_all(force_reload=True)
        if state.get("refresh_token"):
            logger.info("Successfully retrieved refresh token")
            break
        if state.get("error"):
            raise ActionFailure("OAuth authorization failed. Check the browser tab for details.")
    else:
        raise ActionFailure("Timed out waiting for OAuth authorization. Please re-run test connectivity.")

    # Exchange the refresh token for an access token so the API version
    # check (and all subsequent actions) have instance_url + access_token ready.
    if asset.is_test_environment:
        url_get_token = URL_GET_TOKEN_TEST
    else:
        url_get_token = URL_GET_TOKEN
    _exchange_refresh_token(asset, url_get_token)


def _test_connectivity_username_password(soar: SOARClient, asset: Asset) -> None:
    """Legacy username + password OAuth flow."""
    if asset.is_test_environment:
        url_get_token = URL_GET_TOKEN_TEST
    else:
        url_get_token = URL_GET_TOKEN

    try:
        resp = httpx.post(
            url_get_token,
            data={
                "grant_type": "password",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "username": asset.username,
                "password": asset.password,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token request failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(f"Salesforce rejected credentials: {resp_json.get('error_description') or resp_json['error']}")

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]
    logger.info("Successfully obtained access token via username-password flow")


def _test_connectivity_client_credentials(soar: SOARClient, asset: Asset) -> None:
    """Client credentials (server-to-server) OAuth flow."""
    from urllib.parse import urlparse

    domain_url = (asset.domain_url or "").strip()
    if not domain_url:
        raise ActionFailure("My Domain URL must be set when using Client Credentials flow.")
    if "://" not in domain_url:
        domain_url = f"https://{domain_url}"
    parsed = urlparse(domain_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ActionFailure("My Domain URL must be a full HTTPS URL, e.g. https://example.my.salesforce.com")
    if not parsed.netloc.lower().endswith(".my.salesforce.com"):
        raise ActionFailure("My Domain URL must end in .my.salesforce.com. Do not use login.salesforce.com or test.salesforce.com.")

    token_url = f"{parsed.scheme}://{parsed.netloc}/services/oauth2/token"
    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token request failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(f"Salesforce rejected client credentials: {resp_json.get('error_description') or resp_json['error']}")

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]
    logger.info("Successfully obtained access token via client credentials flow")


def _exchange_refresh_token(asset: Asset, token_url: str) -> None:
    """Exchange the stored refresh token for a fresh access token and persist instance_url."""
    refresh_token = asset.auth_state.get("refresh_token")
    if not refresh_token:
        raise ActionFailure("No refresh token found. Re-run test connectivity.")

    try:
        resp = httpx.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": asset.client_id,
                "client_secret": asset.client_secret,
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
            verify=False,  # noqa: S501
        )
        resp_json = resp.json()
    except Exception as e:
        raise ActionFailure(f"Token refresh failed: {e}") from e

    if resp_json.get("error"):
        raise ActionFailure(f"Salesforce rejected token refresh: {resp_json.get('error_description') or resp_json['error']}")

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]

    # Salesforce rotates the refresh token on each use — persist the new one if provided.
    if new_refresh := resp_json.get("refresh_token"):
        asset.auth_state["refresh_token"] = new_refresh


def _get_access_token(asset: Asset) -> str:
    """Return the current access token from auth state."""
    token = asset.auth_state.get("access_token")
    if not token:
        raise ActionFailure("No access token found. Re-run test connectivity.")
    return token


def _get_salesforce_instance_url(asset: Asset) -> str:
    """Return the Salesforce instance URL from auth state."""
    url = asset.auth_state.get("instance_url")
    if not url:
        raise ActionFailure("No instance URL found. Re-run test connectivity.")
    return url

class RunQueryParams(Params):
    query: str = Param(description='SOQL Query')
    endpoint: str = Param(description='Which Query endpoint to use', default='query', value_list=['query', 'queryAll'])

class RunQueryOutput(ActionOutput):
    records: list[str]

@app.action(description='Run a query using the Salesforce Object Query Language (SOQL)', action_type='investigate', verbose='To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>.')
def run_query(params: RunQueryParams, soar: SOARClient, asset: Asset) -> RunQueryOutput:
    raise NotImplementedError()

class CreateObjectParams(Params):
    sobject: str = Param(description='Name of object', primary=True, default='Case', cef_types=['salesforce object name'])
    field_values: str = Param(description='JSON Object of Key-Value pairs to update')

class CreateObjectOutput(ActionOutput):
    id: str = OutputField(cef_types=['salesforce object id'], example_values=['5001I000002SfMMQA0'])
    success: bool

@app.action(description='Create a new Salesforce object', action_type='generic', read_only=False)
def create_object(params: CreateObjectParams, soar: SOARClient, asset: Asset) -> CreateObjectOutput:
    raise NotImplementedError()

class CreateTicketParams(Params):
    parent_case_id: str | None = Param(description='Object ID of Parent Case', primary=True, cef_types=['salesforce object id'])
    subject: str | None = Param(description='Subject')
    priority: str | None = Param(description='Priority', value_list=['High', 'Medium', 'Low'])
    description: str | None = Param(description='Description')
    field_values: str | None = Param(description='JSON Object of Key-Value pairs to update')

class CreateTicketOutput(ActionOutput):
    id: str = OutputField(cef_types=['salesforce object id'], example_values=['5001I000002SfMMQA0'])
    success: bool

@app.action(description='Create a new Case', action_type='generic', read_only=False)
def create_ticket(params: CreateTicketParams, soar: SOARClient, asset: Asset) -> CreateTicketOutput:
    raise NotImplementedError()

class DeleteObjectParams(Params):
    sobject: str = Param(description='Name of object', primary=True, default='Case', cef_types=['salesforce object name'])
    id: str = Param(description='Salesforce Object ID', primary=True, cef_types=['salesforce object id'])

@app.action(description='Delete an object', action_type='generic', read_only=False)
def delete_object(params: DeleteObjectParams, soar: SOARClient, asset: Asset) -> ActionOutput:
    raise NotImplementedError()

class DeleteTicketParams(Params):
    id: str = Param(description='Object ID of the Case', primary=True, cef_types=['salesforce object id'])

@app.action(description='Delete a Case', action_type='generic', read_only=False)
def delete_ticket(params: DeleteTicketParams, soar: SOARClient, asset: Asset) -> ActionOutput:
    raise NotImplementedError()

class UpdateObjectParams(Params):
    sobject: str = Param(description='Name of object', primary=True, default='Case', cef_types=['salesforce object name'])
    id: str = Param(description='Salesforce Object ID', primary=True, cef_types=['salesforce object id'])
    field_values: str | None = Param(description='JSON Object of Key-Value pairs to update')

@app.action(description='Update an object', action_type='generic', read_only=False)
def update_object(params: UpdateObjectParams, soar: SOARClient, asset: Asset) -> ActionOutput:
    raise NotImplementedError()

class UpdateTicketParams(Params):
    id: str = Param(description='Object ID of the Case', primary=True, cef_types=['salesforce object id'])
    parent_case_id: str | None = Param(description='Object ID of Parent Case', primary=True, cef_types=['salesforce object id'])
    subject: str | None = Param(description='Subject')
    priority: str | None = Param(description='Priority', value_list=['High', 'Medium', 'Low'])
    description: str | None = Param(description='Description')
    status: str | None = Param(description='Status', value_list=['New', 'Working', 'Escalated', 'Closed'])
    field_values: str | None = Param(description='JSON Object of Key-Value pairs to update')

@app.action(description='Update a Case', action_type='generic', read_only=False)
def update_ticket(params: UpdateTicketParams, soar: SOARClient, asset: Asset) -> ActionOutput:
    raise NotImplementedError()

class ListObjectsParams(Params):
    sobject: str = Param(description='Name of object', primary=True, default='Case', cef_types=['salesforce object name'])
    view_name: str | None = Param(description='Unique name of a list view', primary=True, cef_types=['salesforce listview name'])
    limit: float | None = Param(description='Paging limit')
    offset: float | None = Param(description='Paging offset')

class IdOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['0033t000035qrSYAAY'])

class ColumnsOutput(ActionOutput):
    Id: IdOutput

class ListObjectsOutput(ActionOutput):
    columns: ColumnsOutput

@app.action(description='Get a list of objects', action_type='investigate', verbose='To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary. Also, this action will only work if the specified object has a list view. If it does not, you could use the <b>run query</b> action instead.')
def list_objects(params: ListObjectsParams, soar: SOARClient, asset: Asset) -> ListObjectsOutput:
    raise NotImplementedError()

class ListTicketsParams(Params):
    view_name: str | None = Param(description='Unique name of a list view', primary=True, cef_types=['salesforce listview name'])
    limit: float | None = Param(description='Paging limit')
    offset: float | None = Param(description='Paging offset')

class CasenumberOutput(ActionOutput):
    value: str = OutputField(example_values=['00001028'])

class ContactidOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['0033t000035qrSWABZ'])

class ContactIdOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['0033t000035qrSWABZ'])

class ContactNameOutput(ActionOutput):
    value: str = OutputField(example_values=['Abcd'])

class CreateddateOutput(ActionOutput):
    value: str = OutputField(example_values=['Thu Nov 30 23:50:55 GMT 2017'])

class IdOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['5001I000002Sd2hQAC'])

class LastmodifieddateOutput(ActionOutput):
    value: str = OutputField(example_values=['Fri Dec 01 00:17:47 GMT 2017'])

class OwneridOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['0051I000000PRsCQAW'])

class OwnerIdOutput(ActionOutput):
    value: str = OutputField(cef_types=['salesforce object id'], example_values=['0051I000000PRsCQAW'])

class OwnerNameoraliasOutput(ActionOutput):
    value: str = OutputField(example_values=['testuser'])

class PriorityOutput(ActionOutput):
    value: str = OutputField(example_values=['Medium'])

class RecordtypeidOutput(ActionOutput):
    value: str = OutputField(example_values=['0121I000000F7aZQAS'])

class StatusOutput(ActionOutput):
    value: str = OutputField(example_values=['In-Progress'])

class SubjectOutput(ActionOutput):
    value: str = OutputField(example_values=['Panic'])

class SystemmodstampOutput(ActionOutput):
    value: str = OutputField(example_values=['Sat Dec 02 11:18:29 GMT 2017'])

class ColumnsOutput(ActionOutput):
    CaseNumber: CasenumberOutput
    ContactId: ContactidOutput
    Contact_Id: ContactIdOutput
    Contact_Name: ContactNameOutput
    CreatedDate: CreateddateOutput
    Id: IdOutput
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
    columns: ColumnsOutput

@app.action(description='Get a list of Cases', action_type='investigate', verbose='To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary.')
def list_tickets(params: ListTicketsParams, soar: SOARClient, asset: Asset) -> ListTicketsOutput:
    raise NotImplementedError()

class GetObjectParams(Params):
    sobject: str = Param(description='Name of object', primary=True, default='Case', cef_types=['salesforce object name'])
    id: str = Param(description='Salesforce Object ID', primary=True, cef_types=['salesforce object id'])

class GetObjectOutput(ActionOutput):
    id: str = OutputField(cef_types=['salesforce object id'], example_values=['5001I000002SfMMQA0'])

@app.action(description='Get info about a Salesforce object', action_type='investigate', verbose='If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.')
def get_object(params: GetObjectParams, soar: SOARClient, asset: Asset) -> GetObjectOutput:
    raise NotImplementedError()

class GetTicketParams(Params):
    id: str = Param(description='Object ID of the Case', primary=True, cef_types=['salesforce object id'])

class AttributesOutput(ActionOutput):
    type: str = OutputField(example_values=['Case'])
    url: str = OutputField(example_values=['/services/data/v41.0/sobjects/Case/5001I000002SfMMQA0'])

class GetTicketOutput(ActionOutput):
    AccountId: str = OutputField(cef_types=['salesforce object id'], example_values=['0013t00001ZyVVTAB4'])
    AssetId: str
    CaseNumber: str = OutputField(example_values=['00001030'])
    Case_Open_minutes__c: float = OutputField(example_values=[4218])
    ClosedDate: str = OutputField(example_values=['2019-06-25T18:59:51.000+0000'])
    Closed_Time_Days__c: str
    ContactEmail: str = OutputField(example_values=['test@example.com'])
    ContactFax: str = OutputField(example_values=['(1) 234 567'])
    ContactId: str = OutputField(cef_types=['salesforce object id'], example_values=['0033t000035qrSWABZ'])
    ContactMobile: str = OutputField(example_values=['(1) 222 333'])
    ContactPhone: str = OutputField(example_values=['(1) 33 444'])
    CreatedById: str = OutputField(cef_types=['salesforce object id'], example_values=['0051I000000PRsCQAW'])
    CreatedDate: str = OutputField(example_values=['2017-12-01T21:32:33.000+0000'])
    Customer_Impacting__c: str
    Date_Reviewed__c: str
    Days_Open__c: float = OutputField(example_values=[3])
    Description: str = OutputField(example_values=['Case Description'])
    Discovery_Method__c: str
    Discovery_Time_Hours__c: str
    EngineeringReqNumber__c: str = OutputField(example_values=['765810'])
    Executive_Summary__c: str
    Id: str = OutputField(cef_types=['salesforce object id'], example_values=['5001I000002SfMMQA0'])
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
    LastModifiedById: str = OutputField(cef_types=['salesforce object id'], example_values=['0051I000000PRsCQAW'])
    LastModifiedDate: str = OutputField(example_values=['2017-12-01T21:32:33.000+0000'])
    LastReferencedDate: str = OutputField(example_values=['2017-12-01T21:33:05.000+0000'])
    LastViewedDate: str = OutputField(example_values=['2017-12-01T21:33:05.000+0000'])
    Origin: str
    OwnerId: str = OutputField(cef_types=['salesforce object id'], example_values=['0051I000000PRsCQAW'])
    ParentId: str = OutputField(cef_types=['salesforce object id'], example_values=['0061I000000PRsCABC'])
    PotentialLiability__c: str = OutputField(example_values=['No'])
    Priority: str = OutputField(example_values=['High'])
    Product__c: str = OutputField(example_values=['GC5555'])
    Reason: str = OutputField(example_values=['Test Complexity'])
    RecordTypeId: str = OutputField(example_values=['0121I000000F7aZQAS'])
    Resolution_Date__c: str
    Resolution_Time_Hours__c: str
    Response_Time_Hours__c: str
    Response_Time_Minutes__c: float = OutputField(example_values=[4218])
    SITrack_Response_Task__c: str
    SITracker_Handoff_Notes__c: str
    SITracker_Include_in_Handoff__c: bool
    SLAViolation__c: str
    Status: str = OutputField(example_values=['New'])
    Subject: str = OutputField(example_values=['Case Subject'])
    SuppliedCompany: str
    SuppliedEmail: str
    SuppliedName: str
    SuppliedPhone: str
    SystemModstamp: str = OutputField(example_values=['2017-12-02T11:18:29.000+0000'])
    Type: str = OutputField(example_values=['Electrical'])
    attributes: AttributesOutput

@app.action(description='Get info about a Case', action_type='investigate', verbose='If you have custom fields added to a Case, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.')
def get_ticket(params: GetTicketParams, soar: SOARClient, asset: Asset) -> GetTicketOutput:
    raise NotImplementedError()

class PostChatterParams(Params):
    id: str = Param(description='Object ID of the Case', primary=True, cef_types=['salesforce object id'])
    title: str | None = Param(description='Title of the post')
    body: str = Param(description='Body of the post')

class PostChatterOutput(ActionOutput):
    id: str = OutputField(cef_types=['salesforce object id'], example_values=['0D51I00000Jw1tnSAB'])
    success: bool

@app.action(description='Post on the Chatter feed for a specified case', action_type='generic', read_only=False)
def post_chatter(params: PostChatterParams, soar: SOARClient, asset: Asset) -> PostChatterOutput:
    raise NotImplementedError()
if __name__ == '__main__':
    app.cli()