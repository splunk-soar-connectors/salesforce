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
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import ListSummary, ListColumnsOutput, ListColumnIdValue
from .list_objects import _extract_id_from_record, _validate_list_params


class ListTicketsParams(Params):
    view_name: str | None = Param(
        description="Unique name of a list view",
        primary=True,
        cef_types=["salesforce listview name"],
    )
    limit: float | None = Param(description="Paging limit")
    offset: float | None = Param(description="Paging offset")


class ListTicketsOutput(ActionOutput):
    columns: ListColumnsOutput


def list_tickets(
    params: ListTicketsParams, soar: SOARClient, asset: Asset
) -> list[ListTicketsOutput]:
    client = SalesforceClient(asset)
    if not params.view_name:
        list_views = client.list_views("Case")
        names = [v.get("developerName", v.get("label", "")) for v in list_views]
        soar.set_summary(ListSummary(num_objects=len(names), view_names=names))
        soar.set_message(
            f"No view_name specified. Available list views for Case: {', '.join(names)}"
        )
        return []
    limit, offset = _validate_list_params(params.limit, params.offset)
    view_id = client.resolve_list_view_id("Case", params.view_name)
    data = client.list_view_results("Case", view_id, limit=limit, offset=offset)
    records = data.get("records", [])
    soar.set_summary(ListSummary(num_objects=len(records), view_names=None))
    soar.set_message(f"Successfully fetched {len(records)} Cases")
    return [
        ListTicketsOutput(
            columns=ListColumnsOutput(
                Id=ListColumnIdValue(value=_extract_id_from_record(r))
            )
        )
        for r in records
    ]
