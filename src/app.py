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
import base64
import hashlib
import json
import secrets
import time
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
from soar_sdk.params import Param, Params, OnPollParams
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

from .salesforce_client import SalesforceClient
from . import views

logger = getLogger()

SALESFORCE_PKCE_VERIFIER_BYTES = 96
SALESFORCE_DEFAULT_TIMEOUT = 30

URL_GET_CODE = "https://login.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN = "https://login.salesforce.com/services/oauth2/token"  # noqa: S105
URL_GET_CODE_TEST = "https://test.salesforce.com/services/oauth2/authorize"
URL_GET_TOKEN_TEST = "https://test.salesforce.com/services/oauth2/token"  # noqa: S105


class Asset(BaseAsset):
    client_id: str = AssetField(
        description="Salesforce OAuth client identifier, also called the consumer key.",
        category=FieldCategory.CONNECTIVITY,
    )
    client_secret: str = AssetField(
        description="Salesforce OAuth client secret, also called the consumer secret.",
        sensitive=True,
        category=FieldCategory.CONNECTIVITY,
    )
    use_client_credentials: bool | None = AssetField(
        description="Use Salesforce Client Credentials OAuth flow.",
        default=False,
        category=FieldCategory.CONNECTIVITY,
    )
    domain_url: str | None = AssetField(
        description="Salesforce Current My Domain URL used for Client Credentials flow.",
        default=None,
        required=False,
        category=FieldCategory.CONNECTIVITY,
    )
    username: str | None = AssetField(
        description="(Legacy) Username for username-password OAuth flow. Not required for External Client App setup.",
        default=None,
        required=False,
        category=FieldCategory.CONNECTIVITY,
    )
    password: str | None = AssetField(
        description="(Legacy) Password with security token appended. Not required for External Client App setup.",
        sensitive=True,
        default=None,
        required=False,
        category=FieldCategory.CONNECTIVITY,
    )
    is_test_environment: bool | None = AssetField(
        description="Use a Salesforce test environment for browser OAuth and legacy username-password flows",
        default=False,
        category=FieldCategory.CONNECTIVITY,
    )
    poll_sobject: str | None = AssetField(
        description="Poll for this Salesforce Object",
        default="Case",
        category=FieldCategory.INGEST,
    )
    poll_view_name: str | None = AssetField(
        description="Poll this List View",
        default=None,
        required=False,
        category=FieldCategory.INGEST,
    )
    first_ingestion_max: float | None = AssetField(
        description="Get this many results on first ingestion",
        default=10.0,
        category=FieldCategory.INGEST,
    )
    cef_name_map: str | None = AssetField(
        description="Mapping of Salesforce to CEF fields (JSON file)",
        default=None,
        required=False,
        is_file=True,
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
    asset_cls=Asset,
).enable_webhooks(default_requires_auth=False)


@app.webhook("/redirect", allowed_methods=["GET"])
def handle_redirect(request: WebhookRequest) -> WebhookResponse:
    """Bounces the browser to the Salesforce authorization URL stored in auth_state."""
    asset: Asset = request.asset
    url = asset.auth_state.get("url")
    if not url:
        return WebhookResponse.text_response(
            "ERROR: No authorization URL found. Re-run test connectivity.",
            status_code=400,
        )
    return WebhookResponse(status_code=302, content="", headers=[("Location", url)])


@app.webhook("/start_oauth", allowed_methods=["GET"])
def handle_start_oauth(request: WebhookRequest) -> WebhookResponse:
    """Receives the OAuth callback from Salesforce, exchanges the code for a refresh token."""
    asset: Asset = request.asset
    auth_state = asset.auth_state

    code = (request.query.get("code") or [""])[0]
    if not code:
        error = (
            request.query.get("error_description")
            or request.query.get("error")
            or ["Unknown error"]
        )[0]
        auth_state["error"] = True
        return WebhookResponse.text_response(
            f"Authentication failed: {error}", status_code=401
        )

    url_get_token = auth_state.get("url_get_token")
    if not url_get_token:
        auth_state["error"] = True
        return WebhookResponse.text_response(
            "ERROR: State missing token URL. Re-run test connectivity.", status_code=400
        )

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
        return WebhookResponse.text_response(
            f"Error retrieving OAuth token: {e}", status_code=401
        )

    sf_error = resp_json.get("error_description") or resp_json.get("error")
    if sf_error:
        auth_state["error"] = True
        return WebhookResponse.text_response(
            f"Salesforce token exchange failed: {sf_error}", status_code=401
        )

    refresh_token = resp_json.get("refresh_token")
    if not refresh_token:
        auth_state["error"] = True
        return WebhookResponse.text_response(
            "Unable to retrieve refresh token. Check OAuth scopes include refresh_token.",
            status_code=401,
        )

    auth_state["refresh_token"] = refresh_token
    auth_state.pop("url", None)
    auth_state.pop("url_get_token", None)
    auth_state.pop("client_id", None)
    auth_state.pop("client_secret", None)
    auth_state.pop("redirect_uri", None)
    auth_state.pop("code_verifier", None)
    auth_state.pop("error", None)

    return WebhookResponse.text_response("You can now close this page.")


SEVERITY_MAP = {
    "severity 1 (high impact)": "high",
    "severity 2 (medium impact)": "medium",
    "severity 3 (low impact)": "low",
    "severity 4 (false positive)": "low",
}
SENSITIVITY_MAP = {
    "sensitive": "red",
    "not sensitive": "white",
}


@app.on_poll()
def on_poll(
    params: OnPollParams, soar: SOARClient, asset: Asset
) -> Iterator[Container | Artifact]:
    sobject = asset.poll_sobject or "Case"
    view_name = asset.poll_view_name
    include_view_date = (
        asset.last_view_date if asset.last_view_date is not None else True
    )
    container_label: str | None = (
        app.actions_manager.get_config().get("ingest", {}).get("container_label")
    )

    if not view_name:
        raise ActionFailure("poll_view_name must be set in asset configuration.")

    # Load the CEF field name map from the JSON file if configured
    cef_name_map: dict[str, str] = {}
    if asset.cef_name_map:
        try:
            cef_name_map = json.loads(asset.cef_name_map)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"cef_name_map is not valid JSON: {e}") from e
        for k, v in cef_name_map.items():
            if not isinstance(v, str) or not k.strip() or not v.strip():
                raise ActionFailure(
                    "cef_name_map must contain non-empty string keys and values."
                )

    is_manual = params.is_manual_poll()

    if is_manual:
        # Poll Now: always start from offset 0, respect container_count cap
        offset = 0
        max_records = int(params.container_count) if params.container_count else 10
    else:
        # Scheduled poll: resume from last saved offset
        offset = int(asset.ingest_state.get("cur_offset") or 0)
        # On very first run, cap to first_ingestion_max
        max_records = None
        if offset == 0:
            max_records = int(asset.first_ingestion_max or 10)

    logger.info(
        f"Polling {sobject} list view '{view_name}' from offset {offset}, max={max_records}"
    )

    client = SalesforceClient(asset)
    new_offset, list_records = client.list_view_records_paged(
        sobject, view_name, offset=offset, max_records=max_records
    )

    logger.info(
        f"Fetched {len(list_records)} list-view records from '{view_name}' (offset={offset}, max={max_records}); container_label={container_label!r}"
    )

    if not list_records:
        logger.info("No new records found.")
        if not is_manual:
            asset.ingest_state["cur_offset"] = new_offset
        return

    # Extract IDs from the list-view summary records and fetch full objects in batches of 25
    record_ids = [_id for row in list_records if (_id := _extract_id_from_record(row))]

    logger.info(f"Extracted {len(record_ids)} record IDs from list-view rows")

    full_records: list[dict] = []
    for i in range(0, len(record_ids), 25):
        batch = client.batch_get(sobject, record_ids[i : i + 25])
        full_records.extend(batch)

    logger.info(f"Fetched {len(full_records)} full {sobject} records")

    for record in full_records:
        cef: dict = {}
        cef_types: dict = {}

        for k, v in record.items():
            if k == "attributes":
                continue
            cef_key = cef_name_map.get(k, k)
            cef[cef_key] = v
            # Auto-tag any field ending in "Id" as a salesforce object id CEF type
            if k.endswith("Id") and v is not None:
                cef_types[cef_key] = ["salesforce object id"]

        if not include_view_date:
            cef.pop("LastViewedDate", None)
            cef.pop("LastReferencedDate", None)

        # Container name: prefer Subject, fall back to CaseNumber / Id
        container_name = (
            record.get("Subject")
            or f"Salesforce {sobject} # {record.get('CaseNumber') or record.get('Id', '')}"
        )

        record_id = record.get("Id", "")
        container_sdi = hashlib.sha256(f"{sobject}{record_id}".encode()).hexdigest()
        artifact_sdi = hashlib.sha256(
            json.dumps(cef, sort_keys=True).encode()
        ).hexdigest()

        container = Container(
            name=container_name,
            label=container_label,
            source_data_identifier=container_sdi,
            severity=SEVERITY_MAP.get(
                (record.get("Incident_Severity__c") or "").lower()
            ),
            sensitivity=SENSITIVITY_MAP.get(
                (record.get("Incident_Sensitivity__c") or "").lower()
            ),
        )
        yield container

        yield Artifact(
            name=sobject,
            label="event",
            source_data_identifier=artifact_sdi,
            cef=cef,
            cef_types=cef_types if cef_types else None,
        )

    # Persist offset only for scheduled polls so the next run continues where this left off
    if not is_manual:
        asset.ingest_state["cur_offset"] = new_offset
        logger.info(f"Saved poll offset: {new_offset}")


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
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(SALESFORCE_PKCE_VERIFIER_BYTES))
        .rstrip(b"=")
        .decode()
    )
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("ascii")).digest())
        .rstrip(b"=")
        .decode()
    )

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
    auth_state.put_all(
        {
            "url": full_auth_url,
            "url_get_token": url_get_token,
            "client_id": asset.client_id,
            "client_secret": asset.client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        }
    )

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
            raise ActionFailure(
                "OAuth authorization failed. Check the browser tab for details."
            )
    else:
        raise ActionFailure(
            "Timed out waiting for OAuth authorization. Please re-run test connectivity."
        )

    # Exchange the refresh token for an access token so the API version
    # check (and all subsequent actions) have instance_url + access_token ready.
    url_get_token = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN
    _exchange_refresh_token(asset, url_get_token)


def _test_connectivity_username_password(soar: SOARClient, asset: Asset) -> None:
    """Legacy username + password OAuth flow."""
    url_get_token = URL_GET_TOKEN_TEST if asset.is_test_environment else URL_GET_TOKEN

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
        raise ActionFailure(
            f"Salesforce rejected credentials: {resp_json.get('error_description') or resp_json['error']}"
        )

    asset.auth_state["access_token"] = resp_json["access_token"]
    asset.auth_state["instance_url"] = resp_json["instance_url"]
    logger.info("Successfully obtained access token via username-password flow")


def _test_connectivity_client_credentials(soar: SOARClient, asset: Asset) -> None:
    """Client credentials (server-to-server) OAuth flow."""
    from urllib.parse import urlparse

    domain_url = (asset.domain_url or "").strip()
    if not domain_url:
        raise ActionFailure(
            "My Domain URL must be set when using Client Credentials flow."
        )
    if "://" not in domain_url:
        domain_url = f"https://{domain_url}"
    parsed = urlparse(domain_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ActionFailure(
            "My Domain URL must be a full HTTPS URL, e.g. https://example.my.salesforce.com"
        )
    if not parsed.netloc.lower().endswith(".my.salesforce.com"):
        raise ActionFailure(
            "My Domain URL must end in .my.salesforce.com. Do not use login.salesforce.com or test.salesforce.com."
        )

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
        raise ActionFailure(
            f"Salesforce rejected client credentials: {resp_json.get('error_description') or resp_json['error']}"
        )

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
        raise ActionFailure(
            f"Salesforce rejected token refresh: {resp_json.get('error_description') or resp_json['error']}"
        )

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
    query: str = Param(description="SOQL Query")
    endpoint: str = Param(
        description="Which Query endpoint to use",
        default="query",
        value_list=["query", "queryAll"],
    )


class RunQuerySummary(ActionOutput):
    num_objects: int = OutputField(example_values=[5])


class RunQueryOutput(ActionOutput):
    records: list[str]


@app.action(
    description="Run a query using the Salesforce Object Query Language (SOQL)",
    action_type="investigate",
    verbose="To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>.",
    view_handler=app.view_handler()(views.run_query_view),
)
def run_query(params: RunQueryParams, soar: SOARClient, asset: Asset) -> RunQueryOutput:
    client = SalesforceClient(asset)
    records = client.query(params.query, endpoint=params.endpoint)
    soar.set_summary(RunQuerySummary(num_objects=len(records)))
    soar.set_message(f"Successfully retrieved {len(records)} record(s)")
    return RunQueryOutput(records=[str(r) for r in records])


class CreateObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    field_values: str = Param(description="JSON Object of Key-Value pairs to update")


class CreateSummary(ActionOutput):
    obj_id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )


class CreateObjectOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


@app.action(
    description="Create a new Salesforce object", action_type="generic", read_only=False
)
def create_object(
    params: CreateObjectParams, soar: SOARClient, asset: Asset
) -> CreateObjectOutput:
    try:
        fields = json.loads(params.field_values)
    except (json.JSONDecodeError, TypeError) as e:
        raise ActionFailure(f"field_values must be valid JSON: {e}") from e
    client = SalesforceClient(asset)
    result = client.create(params.sobject, fields)
    obj_id = result["id"]
    soar.set_summary(CreateSummary(obj_id=obj_id))
    soar.set_message(f"Successfully created a new {params.sobject}")
    return CreateObjectOutput(id=obj_id, success=result.get("success", True))


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


@app.action(description="Create a new Case", action_type="generic", read_only=False)
def create_ticket(
    params: CreateTicketParams, soar: SOARClient, asset: Asset
) -> CreateTicketOutput:
    fields: dict = {}
    if params.parent_case_id:
        fields["ParentId"] = params.parent_case_id
    if params.subject:
        fields["Subject"] = params.subject
    if params.priority:
        fields["Priority"] = params.priority
    if params.description:
        fields["Description"] = params.description
    if params.field_values:
        try:
            extra = json.loads(params.field_values)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"field_values must be valid JSON: {e}") from e
        fields.update(extra)
    client = SalesforceClient(asset)
    result = client.create("Case", fields)
    obj_id = result["id"]
    soar.set_summary(CreateSummary(obj_id=obj_id))
    soar.set_message("Successfully created a new Case")
    return CreateTicketOutput(id=obj_id, success=result.get("success", True))


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


@app.action(description="Delete an object", action_type="generic", read_only=False)
def delete_object(
    params: DeleteObjectParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    SalesforceClient(asset).delete(params.sobject, params.id)
    soar.set_message(f"Successfully deleted {params.sobject}")
    return ActionOutput()


class DeleteTicketParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )


@app.action(description="Delete a Case", action_type="generic", read_only=False)
def delete_ticket(
    params: DeleteTicketParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    SalesforceClient(asset).delete("Case", params.id)
    soar.set_message("Successfully deleted the Case")
    return ActionOutput()


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


@app.action(description="Update an object", action_type="generic", read_only=False)
def update_object(
    params: UpdateObjectParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    if not params.field_values:
        raise ActionFailure("field_values is required to update an object.")
    try:
        fields = json.loads(params.field_values)
    except (json.JSONDecodeError, TypeError) as e:
        raise ActionFailure(f"field_values must be valid JSON: {e}") from e
    SalesforceClient(asset).update(params.sobject, params.id, fields)
    soar.set_summary(CreateSummary(obj_id=params.id))
    soar.set_message(f"Successfully updated the {params.sobject}")
    return ActionOutput()


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


@app.action(description="Update a Case", action_type="generic", read_only=False)
def update_ticket(
    params: UpdateTicketParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    fields: dict = {}
    if params.parent_case_id:
        fields["ParentId"] = params.parent_case_id
    if params.subject:
        fields["Subject"] = params.subject
    if params.priority:
        fields["Priority"] = params.priority
    if params.description:
        fields["Description"] = params.description
    if params.status:
        fields["Status"] = params.status
    if params.field_values:
        try:
            extra = json.loads(params.field_values)
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"field_values must be valid JSON: {e}") from e
        fields.update(extra)
    if not fields:
        raise ActionFailure("Provide at least one field to update.")
    SalesforceClient(asset).update("Case", params.id, fields)
    soar.set_summary(CreateSummary(obj_id=params.id))
    soar.set_message("Successfully updated the Case")
    return ActionOutput()


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


class ListSummary(ActionOutput):
    num_objects: int = OutputField(example_values=[5])
    view_names: list[str] | None = OutputField(
        example_values=[["All", "My Cases", "Today's Cases"]]
    )


class ListColumnIdValue(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )


class ListColumnsOutput(ActionOutput):
    Id: ListColumnIdValue


class ListRecordOutput(ActionOutput):
    columns: ListColumnsOutput


class ListObjectsOutput(ActionOutput):
    columns: ListColumnsOutput


def _extract_id_from_record(r: dict) -> str:
    for col in r.get("columns", []):
        if col.get("fieldNameOrPath") == "Id":
            return col.get("value", "")
    return r.get("fields", {}).get("Id", {}).get("value", "")


def _validate_list_params(limit, offset) -> tuple[int | None, int | None]:
    if limit is not None:
        lim = int(limit)
        if lim <= 0:
            raise ActionFailure("limit must be a positive integer.")
        return lim, int(offset) if offset is not None else None
    if offset is not None:
        off = int(offset)
        if off < 0:
            raise ActionFailure("offset must be a non-negative integer.")
        return None, off
    return None, None


@app.action(
    description="Get a list of objects",
    action_type="investigate",
    verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary. Also, this action will only work if the specified object has a list view. If it does not, you could use the <b>run query</b> action instead.",
    view_handler=app.view_handler()(views.list_objects_view),
)
def list_objects(
    params: ListObjectsParams, soar: SOARClient, asset: Asset
) -> list[ListObjectsOutput]:
    client = SalesforceClient(asset)
    if not params.view_name:
        views = client.list_views(params.sobject)
        names = [v.get("developerName", v.get("label", "")) for v in views]
        soar.set_summary(ListSummary(num_objects=len(names), view_names=names))
        soar.set_message(
            f"No view_name specified. Available list views for {params.sobject}: {', '.join(names)}"
        )
        return []
    limit, offset = _validate_list_params(params.limit, params.offset)
    view_id = client.resolve_list_view_id(params.sobject, params.view_name)
    data = client.list_view_results(params.sobject, view_id, limit=limit, offset=offset)
    records = data.get("records", [])
    soar.set_summary(ListSummary(num_objects=len(records), view_names=None))
    soar.set_message(f"Successfully fetched a list of {params.sobject} objects")
    return [
        ListObjectsOutput(
            columns=ListColumnsOutput(
                Id=ListColumnIdValue(value=_extract_id_from_record(r))
            )
        )
        for r in records
    ]


class ListTicketsParams(Params):
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class ListTicketsOutput(ActionOutput):
    columns: ListColumnsOutput


@app.action(
    description="Get a list of Cases",
    action_type="investigate",
    verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary.",
)
def list_tickets(
    params: ListTicketsParams, soar: SOARClient, asset: Asset
) -> list[ListTicketsOutput]:
    client = SalesforceClient(asset)
    if not params.view_name:
        views = client.list_views("Case")
        names = [v.get("developerName", v.get("label", "")) for v in views]
        soar.set_summary(ListSummary(num_objects=len(names), view_names=names))
        soar.set_message(
            f"No view_name specified. Available list views for Case: {', '.join(names)}"
        )
        return []
    limit, offset = _validate_list_params(params.limit, params.offset)
    view_id = client.resolve_list_view_id("Case", params.view_name)
    data = client.list_view_results("Case", view_id, limit=limit, offset=offset)
    records = data.get("records", [])
    soar.set_summary(ListSummary(num_objects=len(records), view_names=None))
    soar.set_message(f"Successfully fetched {len(records)} Cases")
    return [
        ListTicketsOutput(
            columns=ListColumnsOutput(
                Id=ListColumnIdValue(value=_extract_id_from_record(r))
            )
        )
        for r in records
    ]


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


@app.action(
    description="Get info about a Salesforce object",
    action_type="investigate",
    verbose="If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
    view_handler=app.view_handler()(views.get_object_view),
)
def get_object(
    params: GetObjectParams, soar: SOARClient, asset: Asset
) -> GetObjectOutput:
    record = SalesforceClient(asset).get(params.sobject, params.id)
    soar.set_message(f"Successfully retrieved {params.sobject}")
    return GetObjectOutput(id=record.get("Id", params.id))


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
    # Always-present fields on an existing Case
    Id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    CaseNumber: str = OutputField(example_values=["00001030"])
    OwnerId: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0051I000000PRsCQAW"]
    )
    CreatedDate: str = OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    LastModifiedDate: str = OutputField(example_values=["2017-12-01T21:32:33.000+0000"])
    SystemModstamp: str = OutputField(example_values=["2017-12-02T11:18:29.000+0000"])
    IsClosed: bool = False
    IsDeleted: bool = False
    IsEscalated: bool = False
    # Optional standard fields
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
    CreatedById: str | None = None
    Customer_Impacting__c: str | None = None
    Date_Reviewed__c: str | None = None
    Days_Open__c: float | None = None
    Description: str | None = None
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
    Subject: str | None = None
    SuppliedCompany: str | None = None
    SuppliedEmail: str | None = None
    SuppliedName: str | None = None
    SuppliedPhone: str | None = None
    Type: str | None = None
    attributes: AttributesOutput | None = None


@app.action(
    description="Get info about a Case",
    action_type="investigate",
    verbose="If you have custom fields added to a Case, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
    view_handler=app.view_handler()(views.get_ticket_view),
)
def get_ticket(
    params: GetTicketParams, soar: SOARClient, asset: Asset
) -> GetTicketOutput:
    record = SalesforceClient(asset).get("Case", params.id)
    soar.set_message("Successfully retrieved Case")
    return GetTicketOutput(**{k: v for k, v in record.items() if v is not None})


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


@app.action(
    description="Post on the Chatter feed for a specified case",
    action_type="generic",
    read_only=False,
)
def post_chatter(
    params: PostChatterParams, soar: SOARClient, asset: Asset
) -> PostChatterOutput:
    result = SalesforceClient(asset).post_chatter(
        params.id, params.body, title=params.title
    )
    soar.set_message("Successfully posted to chatter")
    return PostChatterOutput(id=result["id"], success=result["success"])


if __name__ == "__main__":
    app.cli()
