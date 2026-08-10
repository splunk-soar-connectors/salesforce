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
from soar_sdk.action_results import OutputField, PermissiveActionOutput
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
INVALID_RESPONSE_ERROR = "Salesforce returned an unexpected object response"


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


class GetObjectOutput(PermissiveActionOutput):
    Id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )


def get_object(
    params: GetObjectParams, soar: SOARClient, asset: Asset
) -> GetObjectOutput:
    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    token = get_access_token(asset)
    instance_origin = get_instance_origin(asset, token)
    endpoint = (
        f"{latest_version.rstrip('/')}/sobjects/"
        f"{quote(params.sobject, safe='')}/{quote(params.id, safe='')}/"
    )

    try:
        with httpx.Client(
            base_url=instance_origin,
            auth=StaticTokenAuth(token),
            timeout=SALESFORCE_DEFAULT_TIMEOUT,
        ) as client:
            response = client.get(endpoint)
            response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = _salesforce_error_detail(error.response)
        raise ActionFailure(
            f"Salesforce API error {error.response.status_code}: {detail}"
        ) from error
    except httpx.RequestError as error:
        raise ActionFailure(f"Error connecting to Salesforce: {error}") from error

    try:
        record = response.json()
    except ValueError as error:
        raise ActionFailure(INVALID_RESPONSE_ERROR) from error
    if not isinstance(record, dict):
        raise ActionFailure(INVALID_RESPONSE_ERROR)

    soar.set_message(f"Successfully retrieved {params.sobject}")
    return GetObjectOutput.model_validate(record)
