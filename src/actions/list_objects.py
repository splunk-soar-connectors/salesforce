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
from soar_sdk.action_results import ActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import ListSummary, ListColumnsOutput, ListColumnIdValue


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


class ListObjectsOutput(ActionOutput):
    columns: ListColumnsOutput


def _extract_id_from_record(r: dict) -> str:
    for col in r.get("columns", []):
        if col.get("fieldNameOrPath") == "Id":
            return col.get("value", "")
    return r.get("fields", {}).get("Id", {}).get("value", "")


def _validate_list_params(limit, offset) -> tuple[int | None, int | None]:
    if limit is not None:
        lim = int(limit)
        if lim <= 0:
            raise ActionFailure("limit must be a positive integer.")
        return lim, int(offset) if offset is not None else None
    if offset is not None:
        off = int(offset)
        if off < 0:
            raise ActionFailure("offset must be a non-negative integer.")
        return None, off
    return None, None


def list_objects(
    params: ListObjectsParams, soar: SOARClient, asset: Asset
) -> list[ListObjectsOutput]:
    client = SalesforceClient(asset)
    if not params.view_name:
        list_views = client.list_views(params.sobject)
        names = [v.get("developerName", v.get("label", "")) for v in list_views]
        soar.set_summary(ListSummary(num_objects=len(names), view_names=names))
        soar.set_message(
            f"No view_name specified. Available list views for {params.sobject}: {', '.join(names)}"
        )
        return []
    limit, offset = _validate_list_params(params.limit, params.offset)
    view_id = client.resolve_list_view_id(params.sobject, params.view_name)
    data = client.list_view_results(params.sobject, view_id, limit=limit, offset=offset)
    records = data.get("records", [])
    soar.set_summary(ListSummary(num_objects=len(records), view_names=None))
    soar.set_message(f"Successfully fetched a list of {params.sobject} objects")
    return [
        ListObjectsOutput(
            columns=ListColumnsOutput(
                Id=ListColumnIdValue(value=_extract_id_from_record(r))
            )
        )
        for r in records
    ]
