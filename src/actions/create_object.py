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
from urllib.parse import quote

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..auth import get_salesforce_client
from .utils import request_salesforce_json


MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)
INVALID_RESPONSE_ERROR = "Salesforce returned an unexpected create object response"


class CreateObjectParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    field_values: str = Param(description="JSON Object of Key-Value pairs to update")


class CreateObjectOutput(PermissiveActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SfMMQA0"]
    )
    success: bool


class CreateObjectSummary(ActionOutput):
    obj_id: str = OutputField(
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
        column_name="ID",
    )


def create_object(
    params: CreateObjectParams, soar: SOARClient, asset: Asset
) -> CreateObjectOutput:
    try:
        field_values = json.loads(params.field_values)
    except (TypeError, ValueError) as error:
        raise ActionFailure(f"Error reading 'field_values': {error}") from error

    if (
        any(character in params.sobject for character in ("/", "\\", "?", "#"))
        or ".." in params.sobject
    ):
        raise ActionFailure(
            "Invalid value for 'sobject' parameter: must be a single Salesforce path segment"
        )

    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    endpoint = (
        f"{latest_version.rstrip('/')}/sobjects/{quote(params.sobject, safe='')}/"
    )

    with get_salesforce_client(asset) as client:
        response_data = request_salesforce_json(
            client,
            "POST",
            endpoint,
            json=field_values,
            invalid_response_error=INVALID_RESPONSE_ERROR,
        )

    object_id = response_data.get("id")
    if not isinstance(object_id, str):
        raise ActionFailure(INVALID_RESPONSE_ERROR)

    soar.set_summary(CreateObjectSummary(obj_id=object_id))
    soar.set_message(f"Successfully created a new {params.sobject}")
    return CreateObjectOutput.model_validate(response_data)
