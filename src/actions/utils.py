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
import httpx


def _salesforce_error_detail(response: httpx.Response) -> str:
    try:
        response_data = response.json()
    except ValueError:
        response_data = None

    if (
        isinstance(response_data, list)
        and response_data
        and isinstance(response_data[0], dict)
    ):
        detail = response_data[0].get("message") or response.text
    elif isinstance(response_data, dict):
        detail = response_data.get("message") or response.text
    else:
        detail = response.text

    return " ".join(str(detail).split())
