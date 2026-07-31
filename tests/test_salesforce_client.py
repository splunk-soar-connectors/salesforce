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
from src.app import _extract_record_ids
from src.salesforce_client import _partition_batch_results


def test_partition_batch_results_preserves_trailing_ids() -> None:
    records, failed_ids = _partition_batch_results(
        "Case",
        ["one", "two", "three"],
        [{"statusCode": 200, "result": {"Id": "one"}}],
    )

    assert records == [{"Id": "one"}]
    assert failed_ids == ["two", "three"]


def test_partition_batch_results_retries_errors_and_malformed_successes() -> None:
    records, failed_ids = _partition_batch_results(
        "Case",
        ["one", "two", "three"],
        [
            {"statusCode": 404, "result": [{"message": "not found"}]},
            {"statusCode": 200, "result": None},
            {"statusCode": 200, "result": {"Id": "three"}},
        ],
    )

    assert records == [{"Id": "three"}]
    assert failed_ids == ["one", "two"]


def test_partition_batch_results_retries_all_ids_for_invalid_results() -> None:
    records, failed_ids = _partition_batch_results("Case", ["one", "two"], None)

    assert records == []
    assert failed_ids == ["one", "two"]


def test_extract_record_ids_reports_first_missing_row() -> None:
    record_ids, first_missing_index = _extract_record_ids(
        [
            {"columns": [{"fieldNameOrPath": "Id", "value": "one"}]},
            {"columns": [{"fieldNameOrPath": "Subject", "value": "missing"}]},
            {"fields": {"Id": {"value": "three"}}},
            {},
        ]
    )

    assert record_ids == ["one", "three"]
    assert first_missing_index == 1
