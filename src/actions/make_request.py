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
from soar_sdk.action_results import MakeRequestOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import MakeRequestParams, Param

from ..asset import Asset
from ..auth import SALESFORCE_DEFAULT_TIMEOUT, get_salesforce_client


MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)


class SalesforceMakeRequestParams(MakeRequestParams):
    endpoint: str = Param(
        description=(
            "Salesforce REST API endpoint to call, relative to the instance URL "
            "and API version. Example: '/sobjects/Case' or "
            "'/query?q=SELECT+Id+FROM+Case'"
        ),
        required=True,
    )


def make_request(
    params: SalesforceMakeRequestParams, soar: SOARClient, asset: Asset
) -> MakeRequestOutput:
    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    endpoint = f"{latest_version.rstrip('/')}/{params.endpoint.lstrip('/')}"
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if params.headers:
        try:
            parsed_headers = json.loads(params.headers)
        except (json.JSONDecodeError, TypeError) as error:
            raise ActionFailure(f"Invalid JSON in headers: {error}") from error
        if not isinstance(parsed_headers, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parsed_headers.items()
        ):
            raise ActionFailure("Invalid JSON in headers: expected a string map")
        if any(key.lower() == "content-type" for key in parsed_headers):
            headers.pop("Content-Type")
        headers.update(parsed_headers)

    query_params: dict[str, str | int | float | bool | None] | None = None
    if params.query_parameters:
        try:
            parsed_query_params = json.loads(params.query_parameters)
        except (json.JSONDecodeError, TypeError):
            query_string = params.query_parameters.lstrip("?")
            endpoint = f"{endpoint}{'&' if '?' in endpoint else '?'}{query_string}"
        else:
            if not isinstance(parsed_query_params, dict) or not all(
                isinstance(key, str)
                and (value is None or isinstance(value, str | int | float | bool))
                for key, value in parsed_query_params.items()
            ):
                raise ActionFailure(
                    "Invalid JSON in query parameters: expected an object of scalar values"
                )
            query_params = parsed_query_params

    content: str | None = None
    json_body: object | None = None
    if params.body:
        content_type = next(
            (
                value
                for key, value in reversed(headers.items())
                if key.lower() == "content-type"
            ),
            "",
        )
        if "json" in content_type.lower():
            try:
                json_body = json.loads(params.body)
            except (json.JSONDecodeError, TypeError) as error:
                raise ActionFailure(f"Invalid JSON in body: {error}") from error
        else:
            content = params.body

    timeout = float(params.timeout or SALESFORCE_DEFAULT_TIMEOUT)
    verify_ssl = bool(params.verify_ssl)
    try:
        with get_salesforce_client(
            asset,
            timeout=timeout,
            verify=verify_ssl,
        ) as client:
            response = client.request(
                params.http_method,
                endpoint,
                headers=headers,
                params=query_params,
                content=content,
                json=json_body,
            )
    except (httpx.RequestError, ValueError) as error:
        raise ActionFailure(f"Request failed: {error}") from error

    soar.set_message(f"Request completed with status {response.status_code}")
    return MakeRequestOutput(
        status_code=response.status_code,
        response_body=response.text,
    )
