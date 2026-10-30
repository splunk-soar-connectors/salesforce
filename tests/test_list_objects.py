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
from src.actions.list_objects import ListObjectsSummary


def test_list_objects_summary_exposes_sdk_output_examples():
    schema = ListObjectsSummary.model_json_schema()["properties"]

    assert schema["num_objects"]["examples"] == [3]
    assert schema["view_names"]["examples"] == ["MyCases"]


def test_list_objects_summary_omits_unset_branch():
    assert ListObjectsSummary(num_objects=3).model_dump() == {"num_objects": 3}
    assert ListObjectsSummary(view_names=["MyCases"]).model_dump() == {
        "view_names": ["MyCases"]
    }
