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


class ListObjectsParams(Params):
    sobject: str = Param(
        description="Name of object",
        primary=True,
        default="Case",
        cef_types=["salesforce object name"],
    )
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class ListObjectsIdOutput(ActionOutput):
    value: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0033t000035qrSYAAY"]
    )


class ListObjectsColumnsOutput(ActionOutput):
    Id: ListObjectsIdOutput


class ListObjectsOutput(ActionOutput):
    columns: ListObjectsColumnsOutput


def list_objects(
    params: ListObjectsParams, soar: SOARClient, asset: Asset
) -> ListObjectsOutput:
    raise NotImplementedError()
