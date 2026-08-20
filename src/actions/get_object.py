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

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import OutputField, PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..auth import get_salesforce_client
from ..state import migrate_legacy_state
from .utils import request_salesforce_json


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
    migrate_legacy_state(asset)
    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    endpoint = (
        f"{latest_version.rstrip('/')}/sobjects/"
        f"{quote(params.sobject, safe='')}/{quote(params.id, safe='')}/"
    )

    with get_salesforce_client(asset) as client:
        record = request_salesforce_json(
            client,
            "GET",
            endpoint,
            invalid_response_error=INVALID_RESPONSE_ERROR,
        )

    soar.set_message(f"Successfully retrieved {params.sobject}")
    return GetObjectOutput.model_validate(record)
