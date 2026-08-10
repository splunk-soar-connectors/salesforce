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
from urllib.parse import quote

import httpx
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.auth import StaticTokenAuth
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..auth import get_access_token, get_instance_origin
from .utils import _salesforce_error_detail


SALESFORCE_DEFAULT_TIMEOUT = 30.0
MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)
INVALID_RESPONSE_ERROR = "Salesforce returned an unexpected query response"


class RunQueryParams(Params):
    query: str = Param(description="SOQL Query", column_name="QUERY")
    endpoint: str = Param(
        description="Which Query endpoint to use",
        default="query",
        value_list=["query", "queryAll"],
        column_name="ENDPOINT",
    )


class RunQueryRecordAttributes(ActionOutput):
    type: str
    url: str


class RunQueryOutput(PermissiveActionOutput):
    attributes: RunQueryRecordAttributes


class RunQuerySummary(ActionOutput):
    num_objects: int = OutputField(example_values=[20])


def _get_query_page(
    client: httpx.Client,
    endpoint: str,
    params: str | None,
) -> dict[str, object]:
    try:
        response = client.get(endpoint, params=params)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = _salesforce_error_detail(error.response)
        raise ActionFailure(
            f"Salesforce API error {error.response.status_code}: {detail}"
        ) from error
    except httpx.RequestError as error:
        raise ActionFailure(f"Error connecting to Salesforce: {error}") from error

    try:
        page = response.json()
    except ValueError as error:
        raise ActionFailure(INVALID_RESPONSE_ERROR) from error
    if not isinstance(page, dict):
        raise ActionFailure(INVALID_RESPONSE_ERROR)
    return page


def run_query(
    params: RunQueryParams, soar: SOARClient, asset: Asset
) -> list[RunQueryOutput]:
    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    token = get_access_token(asset)
    instance_origin = get_instance_origin(asset, token)
    endpoint = f"{latest_version.rstrip('/')}/{quote(params.endpoint, safe='')}/"
    normalized_query = " ".join(params.query.split()).replace(" ", "+")
    query_params: str | None = f"q={normalized_query}"
    records: list[RunQueryOutput] = []

    with httpx.Client(
        base_url=instance_origin,
        auth=StaticTokenAuth(token),
        timeout=SALESFORCE_DEFAULT_TIMEOUT,
    ) as client:
        while True:
            page = _get_query_page(client, endpoint, query_params)
            page_records = page.get("records")
            done = page.get("done")
            if not isinstance(page_records, list) or not isinstance(done, bool):
                raise ActionFailure(INVALID_RESPONSE_ERROR)

            for record in page_records:
                if not isinstance(record, dict):
                    raise ActionFailure(INVALID_RESPONSE_ERROR)
                records.append(RunQueryOutput.model_validate(record))

            if done:
                break

            next_endpoint = page.get("nextRecordsUrl")
            if not isinstance(next_endpoint, str):
                raise ActionFailure(INVALID_RESPONSE_ERROR)
            endpoint = next_endpoint
            query_params = None

    soar.set_summary(RunQuerySummary(num_objects=len(records)))
    soar.set_message("Successfully retrieved query results")
    return records
