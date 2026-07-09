# Copyright (c) 2017-2026 Splunk Inc.
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
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .actions.get_object import GetObjectOutput
from .actions.get_ticket import GetTicketOutput
from .actions.list_objects import ListObjectsOutput
from .actions.run_query import RunQueryOutput

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _get_renderer() -> Environment:
    return Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape(["html"]),
    )


def list_objects_view(results: list[ListObjectsOutput]) -> str:
    rows = []
    for record in results:
        obj_id = record.columns.Id.value
        if obj_id:
            rows.append({"OBJECT ID": obj_id})
    return (
        _get_renderer()
        .get_template("sf_list_objects.html")
        .render(title="List Objects Results", rows=rows)
    )


def run_query_view(results: list[RunQueryOutput]) -> str:
    rows = [{"RECORD": r} for record in results for r in record.records]
    return (
        _get_renderer()
        .get_template("sf_run_query.html")
        .render(title="Run Query Results", rows=rows)
    )


def get_object_view(results: list[GetObjectOutput]) -> str:
    rows = [{"STATUS": "success", "ID": record.id} for record in results]
    return (
        _get_renderer()
        .get_template("sf_get_object.html")
        .render(title="Get Object Results", rows=rows)
    )


def get_ticket_view(results: list[GetTicketOutput]) -> str:
    rows = []
    for record in results:
        row = {
            k.upper(): str(v) for k, v in record.model_dump().items() if v is not None
        }
        if row:
            rows.append(row)
    return (
        _get_renderer()
        .get_template("sf_get_ticket.html")
        .render(title="Get Ticket Results", rows=rows)
    )
