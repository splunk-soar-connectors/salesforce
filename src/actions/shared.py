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
from soar_sdk.action_results import ActionOutput, OutputField


class StatusOutput(ActionOutput):
    status: str = OutputField(column_name="STATUS", example_values=["success"])


class CreateSummary(ActionOutput):
    obj_id: str = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListSummary(ActionOutput):
    num_objects: int = OutputField(example_values=[5])
    view_names: list[str] | None = OutputField(
        example_values=[["All", "My Cases", "Today's Cases"]]
    )


class ListObjectsColumnIdValue(ActionOutput):
    value: str = OutputField(
        column_name="OBJECT ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListTicketsColumnIdValue(ActionOutput):
    value: str = OutputField(
        column_name="ID",
        cef_types=["salesforce object id"],
        example_values=["5001I000002SfMMQA0"],
    )


class ListTicketsColumnStringValue(ActionOutput):
    value: str = OutputField(example_values=[""])


class ListTicketsColumnSubjectValue(ActionOutput):
    value: str = OutputField(column_name="Subject", example_values=[""])


class ListTicketsColumnStatusValue(ActionOutput):
    value: str = OutputField(column_name="Status", example_values=["New"])


class ListTicketsColumnPriorityValue(ActionOutput):
    value: str = OutputField(column_name="Priority", example_values=["High"])


class ListObjectsColumnsOutput(ActionOutput):
    Id: ListObjectsColumnIdValue


class ListTicketsColumnsOutput(ActionOutput):
    Id: ListTicketsColumnIdValue
    Subject: ListTicketsColumnSubjectValue
    Status: ListTicketsColumnStatusValue
    Priority: ListTicketsColumnPriorityValue
