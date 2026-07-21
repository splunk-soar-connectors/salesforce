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
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient


class RunQueryParams(Params):
    endpoint: str = Param(
        description="Which Query endpoint to use",
        default="query",
        value_list=["query", "queryAll"],
        column_name="ENDPOINT",
    )
    query: str = Param(description="SOQL Query", column_name="QUERY")


class RunQuerySummary(ActionOutput):
    num_objects: int = OutputField(example_values=[5])


class RunQueryOutput(ActionOutput):
    records: list[str]


def run_query(params: RunQueryParams, soar: SOARClient, asset: Asset) -> RunQueryOutput:
    client = SalesforceClient(asset)
    records = client.query(params.query, endpoint=params.endpoint)
    soar.set_summary(RunQuerySummary(num_objects=len(records)))
    soar.set_message(f"Successfully retrieved {len(records)} record(s)")
    return RunQueryOutput(records=[str(r) for r in records])
