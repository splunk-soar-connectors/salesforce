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

import httpx
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..auth import get_salesforce_client
from ..state import get_latest_api_version
from .utils import salesforce_error_detail


MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)


def _request_salesforce_update(
    client: httpx.Client, endpoint: str, field_values: object
) -> None:
    try:
        response = client.patch(endpoint, json=field_values)
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        detail = salesforce_error_detail(error.response)
        raise ActionFailure(
            f"Salesforce API error {error.response.status_code}: {detail}"
        ) from error
    except httpx.RequestError as error:
        raise ActionFailure(f"Error connecting to Salesforce: {error}") from error


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


class UpdateObjectSummary(ActionOutput):
    obj_id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["5001I000002SdASQA0"]
    )


def update_object(
    params: UpdateObjectParams, soar: SOARClient, asset: Asset
) -> ActionOutput:
    try:
        field_values = json.loads(params.field_values)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ActionFailure(f"Error reading 'field_values': {error}") from error

    for field_name, value in (("sobject", params.sobject), ("id", params.id)):
        if (
            any(character in value for character in ("/", "\\", "?", "#"))
            or ".." in value
        ):
            raise ActionFailure(
                f"Invalid value for '{field_name}' parameter: must be a single Salesforce path segment"
            )

    latest_version = get_latest_api_version(asset)
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    endpoint = (
        f"{latest_version.rstrip('/')}/sobjects/"
        f"{quote(params.sobject, safe='')}/{quote(params.id, safe='')}/"
    )
    with get_salesforce_client(asset) as client:
        _request_salesforce_update(client, endpoint, field_values)

    soar.set_summary(UpdateObjectSummary(obj_id=params.id))
    soar.set_message(f"Successfully updated the {params.sobject}")
    return ActionOutput()
