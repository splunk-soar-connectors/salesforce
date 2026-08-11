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
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import MakeRequestOutput
from soar_sdk.params import MakeRequestParams, Param

from ..asset import Asset


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
    raise NotImplementedError()
