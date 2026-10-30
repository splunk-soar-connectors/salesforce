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
import pytest
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure

from src.actions.run_query import (
    RunQueryParams,
    RunQueryRecordAttributes,
    RunQuerySummary,
    run_query,
)
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_run_query_live(app: App, asset: Asset) -> None:
    run_test_connectivity(asset)

    records = run_query(
        RunQueryParams(query="SELECT Id FROM User LIMIT 1", endpoint="queryAll"),
        app.soar_client,
        asset,
    )

    assert len(records) == 1
    assert isinstance(records[0].attributes, RunQueryRecordAttributes)
    assert records[0].model_extra is not None
    assert isinstance(records[0].model_extra.get("Id"), str)
    assert app.soar_client.get_summary() == RunQuerySummary(num_objects=1)
    assert app.soar_client.get_message() == "Successfully retrieved query results"

    with pytest.raises(ActionFailure, match="Salesforce API error 400"):
        run_query(
            RunQueryParams(query="not valid SOQL", endpoint="query"),
            app.soar_client,
            asset,
        )
