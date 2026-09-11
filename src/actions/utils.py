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
import httpx
from soar_sdk.exceptions import ActionFailure


def salesforce_error_detail(response: httpx.Response) -> str:
    try:
        response_data = response.json()
    except ValueError:
        response_data = None

    if (
        isinstance(response_data, list)
        and response_data
        and isinstance(response_data[0], dict)
    ):
        detail = response_data[0].get("message") or response.text
    elif isinstance(response_data, dict):
        detail = response_data.get("message") or response.text
    else:
        detail = response.text

    return " ".join(str(detail).split())


def request_salesforce_json(
    client: httpx.Client,
    method: str,
    endpoint: str,
    *,
    invalid_response_error: str,
    params: str | dict[str, str] | None = None,
    json: object | None = None,
) -> dict[str, object]:
    try:
        response = client.request(method, endpoint, params=params, json=json)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = salesforce_error_detail(error.response)
        raise ActionFailure(
            f"Salesforce API error {error.response.status_code}: {detail}"
        ) from error
    except httpx.RequestError as error:
        raise ActionFailure(f"Error connecting to Salesforce: {error}") from error

    try:
        response_data = response.json()
    except ValueError as error:
        raise ActionFailure(invalid_response_error) from error
    if not isinstance(response_data, dict):
        raise ActionFailure(invalid_response_error)
    return response_data
