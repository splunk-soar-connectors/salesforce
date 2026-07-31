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
import json

import httpx

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import MakeRequestParams, Param

from ..asset import Asset
from ..auth import get_request_auth
from ..salesforce_client import SalesforceClient

SALESFORCE_DEFAULT_TIMEOUT = 30


class SalesforceMakeRequestParams(MakeRequestParams):
    endpoint: str = Param(
        description=(
            "Salesforce REST API endpoint to call, relative to the instance URL and API version. "
            "Example: '/sobjects/Case' or '/query?q=SELECT+Id+FROM+Case'"
        ),
        required=True,
    )


class SalesforceMakeRequestOutput(ActionOutput):
    status_code: int = OutputField(example_values=[200])
    response_body: str = OutputField(example_values=['{"totalSize": 1, "records": []}'])


def make_request(
    params: SalesforceMakeRequestParams, soar: SOARClient, asset: Asset
) -> SalesforceMakeRequestOutput:
    client = SalesforceClient(asset)

    endpoint = (
        params.endpoint if params.endpoint.startswith("/") else f"/{params.endpoint}"
    )
    url = f"{client._base_url()}{endpoint}"

    headers: dict = {"Content-Type": "application/json"}
    if params.headers:
        try:
            headers.update(json.loads(params.headers))
        except (json.JSONDecodeError, TypeError) as e:
            raise ActionFailure(f"Invalid JSON in headers: {e}") from e

    query_params = None
    if params.query_parameters:
        try:
            query_params = json.loads(params.query_parameters)
        except (json.JSONDecodeError, TypeError):
            query_string = params.query_parameters.lstrip("?")
            url = f"{url}{'&' if '?' in url else '?'}{query_string}"

    body = None
    json_body = None
    if params.body:
        if "json" in headers.get("Content-Type", "").lower():
            try:
                json_body = json.loads(params.body)
            except (json.JSONDecodeError, TypeError) as e:
                raise ActionFailure(f"Invalid JSON in body: {e}") from e
        else:
            body = params.body

    timeout = params.timeout or SALESFORCE_DEFAULT_TIMEOUT

    verify_ssl = bool(params.verify_ssl) if params.verify_ssl is not None else False
    try:
        resp = httpx.request(
            method=params.http_method,
            url=url,
            auth=get_request_auth(asset),
            headers=headers,
            params=query_params,
            data=body,
            json=json_body,
            timeout=timeout,
            verify=verify_ssl,
        )
    except Exception as e:
        raise ActionFailure(f"Request failed: {e}") from e

    soar.set_message(f"Request completed with status {resp.status_code}")
    return SalesforceMakeRequestOutput(
        status_code=resp.status_code,
        response_body=resp.text,
    )
