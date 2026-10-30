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
import pytest
from soar_sdk.action_results import ActionResult
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import OnPollParams

from src.actions.get_ticket import GetTicketOutput
from src.actions.list_tickets import ListTicketsOutput
from src.actions.make_request import merge_query_parameters
from src.actions.on_poll import failed_poll_retry_offset, is_manual_poll
from src.actions.run_query import (
    RunQueryOutput,
    RunQueryParams,
    query_failure_result,
)
from src.actions.utils import salesforce_error_detail


def test_failed_poll_retries_last_buffered_artifact() -> None:
    assert failed_poll_retry_offset(100, [2], [(0, {}), (1, {})]) == 101


def test_query_failure_result_retains_completed_pages() -> None:
    params = RunQueryParams(query="SELECT Id FROM Case")
    records = [
        RunQueryOutput.model_validate(
            {
                "attributes": {"type": "Case", "url": "/Case/1"},
                "Id": "1",
            }
        )
    ]

    result = query_failure_result(
        params,
        records,
        ActionFailure("later page failed"),
    )

    assert isinstance(result, ActionResult)
    assert result.get_status() is False
    assert result.get_param() == params.model_dump()
    assert result.get_data() == [records[0].model_dump(by_alias=True)]
    assert result.get_summary() == {"num_objects": 1}


def test_salesforce_error_detail_preserves_all_structured_errors() -> None:
    response = httpx.Response(
        400,
        json=[
            {
                "message": "First failure",
                "errorCode": "FIRST_ERROR",
                "fields": ["Subject"],
            },
            {
                "message": "Second failure",
                "errorCode": "SECOND_ERROR",
                "fields": ["Status"],
            },
        ],
    )

    assert json.loads(salesforce_error_detail(response)) == response.json()


def test_provider_variable_ticket_fields_can_be_missing_or_null() -> None:
    ticket = GetTicketOutput.model_validate(
        {
            "Id": "500000000000001",
            "Status": None,
            "custom_provider_field__c": "retained",
        }
    )
    list_row = ListTicketsOutput.model_validate(
        {
            "columns": {
                "Id": {"value": "500000000000001"},
                "Subject": {"value": None},
                "custom_column__c": {"value": "retained"},
            }
        }
    )

    assert ticket.Status is None
    assert ticket.model_dump()["custom_provider_field__c"] == "retained"
    assert list_row.columns is not None
    assert list_row.columns.Subject is not None
    assert list_row.columns.Subject.value is None
    assert list_row.columns.model_dump()["custom_column__c"] == {"value": "retained"}


def test_json_query_parameters_merge_with_endpoint_query_and_take_precedence() -> None:
    endpoint, query_params = merge_query_parameters(
        "/query?existing=endpoint&override=endpoint",
        {"override": "json", "added": 2},
    )

    assert endpoint == "/query"
    assert query_params == {
        "existing": "endpoint",
        "override": "json",
        "added": 2,
    }


def test_zero_container_count_is_rejected_before_poll_mode_detection() -> None:
    with pytest.raises(ActionFailure, match="non-zero positive integer"):
        is_manual_poll(OnPollParams(container_count=0))
