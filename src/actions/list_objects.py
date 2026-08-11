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
from urllib.parse import quote

from pydantic import Field, model_serializer
from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import (
    ActionOutput,
    OutputField,
    PermissiveActionOutput,
)
from soar_sdk.exceptions import ActionFailure
from soar_sdk.params import Param, Params

from ..asset import Asset
from ..auth import get_salesforce_client
from .utils import request_salesforce_json


MISSING_API_VERSION_ERROR = (
    "Unable to retrieve API version. Has test connectivity been run?"
)
INVALID_RESPONSE_ERROR = "Salesforce returned an unexpected list objects response"
MAX_PAGE_SIZE = 2000


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


class ListObjectsColumnsOutput(PermissiveActionOutput):
    Id: ListObjectsIdOutput


class ListObjectsOutput(PermissiveActionOutput):
    columns: ListObjectsColumnsOutput


class ListObjectsSummary(ActionOutput):
    num_objects: int | None = Field(default=None, examples=[3])
    view_names: list[str] | None = Field(default=None, examples=[["MyCases"]])

    @model_serializer
    def serialize_summary(self) -> dict[str, int | list[str]]:
        summary: dict[str, int | list[str]] = {}
        if self.num_objects is not None:
            summary["num_objects"] = self.num_objects
        if self.view_names is not None:
            summary["view_names"] = self.view_names
        return summary


def _validate_integer(value: float, key: str, *, allow_zero: bool = False) -> int:
    try:
        if not float(value).is_integer():
            raise ValueError
        integer = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ActionFailure(
            f"Please provide a valid integer value in the '{key}' parameter"
        ) from error

    if integer < 0:
        raise ActionFailure(
            f"Please provide a valid non-negative integer value in the '{key}' parameter"
        )
    if not allow_zero and integer == 0:
        raise ActionFailure(f'Please provide non-zero positive integer in "{key}"')
    return integer


def _mogrify_record(record: object) -> ListObjectsOutput:
    if not isinstance(record, dict):
        raise ActionFailure(INVALID_RESPONSE_ERROR)
    columns = record.get("columns")
    if not isinstance(columns, list):
        raise ActionFailure(INVALID_RESPONSE_ERROR)

    mapped_columns: dict[str, object] = {}
    for column in columns:
        if not isinstance(column, dict):
            raise ActionFailure(INVALID_RESPONSE_ERROR)
        field_name = column.get("fieldNameOrPath")
        if not isinstance(field_name, str):
            raise ActionFailure(INVALID_RESPONSE_ERROR)
        mapped_columns[field_name.replace(".", "_")] = {
            key: value for key, value in column.items() if key != "fieldNameOrPath"
        }

    return ListObjectsOutput.model_validate({**record, "columns": mapped_columns})


def list_objects(
    params: ListObjectsParams, soar: SOARClient, asset: Asset
) -> list[ListObjectsOutput]:
    latest_version = asset.cache_state.get("latest_version")
    if not isinstance(latest_version, str) or not latest_version.startswith(
        "/services/data/"
    ):
        raise ActionFailure(MISSING_API_VERSION_ERROR)

    endpoint = (
        f"{latest_version.rstrip('/')}/sobjects/"
        f"{quote(params.sobject, safe='')}/listviews/"
    )
    view_names: list[str] = []
    results_url: str | None = None

    with get_salesforce_client(asset) as client:
        while True:
            page = request_salesforce_json(
                client,
                "GET",
                endpoint,
                invalid_response_error=INVALID_RESPONSE_ERROR,
            )
            listviews = page.get("listviews")
            done = page.get("done")
            if not isinstance(listviews, list) or not isinstance(done, bool):
                raise ActionFailure(INVALID_RESPONSE_ERROR)

            for view in listviews:
                if not isinstance(view, dict):
                    raise ActionFailure(INVALID_RESPONSE_ERROR)
                developer_name = view.get("developerName")
                if not isinstance(developer_name, str):
                    raise ActionFailure(INVALID_RESPONSE_ERROR)
                view_names.append(developer_name)
                if params.view_name == developer_name:
                    candidate_url = view.get("resultsUrl")
                    if not isinstance(candidate_url, str):
                        raise ActionFailure(INVALID_RESPONSE_ERROR)
                    results_url = candidate_url
                    break

            if results_url is not None or done:
                break
            next_endpoint = page.get("nextRecordsUrl")
            if not isinstance(next_endpoint, str):
                raise ActionFailure(INVALID_RESPONSE_ERROR)
            endpoint = next_endpoint

        if results_url is None:
            soar.set_summary(ListObjectsSummary(view_names=view_names))
            if params.view_name:
                raise ActionFailure("Specified list view name was not found")
            soar.set_message("Listed the valid view names")
            return []

        limit = _validate_integer(
            params.limit if params.limit is not None else 25, "limit"
        )
        offset = _validate_integer(
            params.offset if params.offset is not None else 0,
            "offset",
            allow_zero=True,
        )
        records: list[ListObjectsOutput] = []
        offset_error: str | None = None

        while True:
            try:
                page = request_salesforce_json(
                    client,
                    "GET",
                    results_url,
                    params={"limit": str(MAX_PAGE_SIZE), "offset": str(offset)},
                    invalid_response_error=INVALID_RESPONSE_ERROR,
                )
            except ActionFailure as error:
                if "Maximum SOQL offset allowed is" not in str(error):
                    raise
                offset_error = str(error)
                break

            page_records = page.get("records")
            if not isinstance(page_records, list):
                raise ActionFailure(INVALID_RESPONSE_ERROR)
            records.extend(_mogrify_record(record) for record in page_records)

            if len(records) >= limit:
                records = records[:limit]
                break
            if len(page_records) < MAX_PAGE_SIZE:
                break
            offset += MAX_PAGE_SIZE

    soar.set_summary(ListObjectsSummary(num_objects=len(records)))
    if offset_error is not None:
        soar.set_message(
            "Because of the limitation of the offset value in the API, "
            "returning the maximum possible records."
            f"Response from the API: {offset_error}"
        )
    else:
        soar.set_message(f"Successfully fetched a list of {params.sobject} objects")
    return records
