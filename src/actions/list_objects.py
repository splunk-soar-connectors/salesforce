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
from soar_sdk.action_results import PermissiveActionOutput
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..salesforce_client import SalesforceClient
from .shared import ListSummary, ListObjectsColumnsOutput


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
    limit: int | None = Param(description="Paging limit")
    offset: int | None = Param(description="Paging offset")


class ListObjectsOutput(PermissiveActionOutput):
    columns: ListObjectsColumnsOutput


def _mogrify_record(record: dict) -> dict:
    """Convert the columns list into a dict keyed by field name, matching legacy behaviour."""
    columns = record.get("columns", [])
    columns_dict = {
        col["fieldNameOrPath"].replace(".", "_"): {
            k: v for k, v in col.items() if k != "fieldNameOrPath"
        }
        for col in columns
    }
    return {**record, "columns": columns_dict}


def _extract_id_from_record(r: dict) -> str:
    for col in r.get("columns", []):
        if col.get("fieldNameOrPath") == "Id":
            return col.get("value", "")
    return r.get("fields", {}).get("Id", {}).get("value", "")


def _validate_list_params(
    limit: int | None, offset: int | None
) -> tuple[int | None, int | None]:
    if limit is not None and limit <= 0:
        raise ActionFailure(
            "Please provide a valid integer value in the 'limit' parameter"
        )
    if offset is not None and offset < 0:
        raise ActionFailure(
            "Please provide a valid non-negative integer value in the 'offset' parameter"
        )
    return limit, offset


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
    return [ListObjectsOutput.model_validate(_mogrify_record(r)) for r in records]
