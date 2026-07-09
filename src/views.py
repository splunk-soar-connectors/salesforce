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

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def _get_renderer():
    env = Environment(
        loader=FileSystemLoader(_TEMPLATES_DIR),
        trim_blocks=True,
        lstrip_blocks=True,
        autoescape=select_autoescape(["html"]),
    )
    return env


def list_objects_view(provides, all_app_runs, context) -> str:
    context["prerender"] = True
    rows = []
    for _summary, action_results in all_app_runs:
        for ar in action_results:
            for record in ar.get_data():
                columns = record.get("columns", {})
                obj_id = columns.get("Id", {}).get("value", "")
                if obj_id:
                    rows.append({"OBJECT ID": obj_id})
    env = _get_renderer()
    tmpl = env.get_template("sf_list_objects.html")
    return tmpl.render(title="List Objects Results", rows=rows)


def run_query_view(provides, all_app_runs, context) -> str:
    context["prerender"] = True
    rows = []
    for _summary, action_results in all_app_runs:
        for ar in action_results:
            for record in ar.get_data():
                rows.append({"RECORD": str(record)})
    env = _get_renderer()
    tmpl = env.get_template("sf_run_query.html")
    return tmpl.render(title="Run Query Results", rows=rows)


def get_object_view(provides, all_app_runs, context) -> str:
    context["prerender"] = True
    rows = []
    for _summary, action_results in all_app_runs:
        for ar in action_results:
            for record in ar.get_data():
                rows.append(
                    {
                        "STATUS": "success",
                        "ID": record.get("id", ""),
                    }
                )
    env = _get_renderer()
    tmpl = env.get_template("sf_get_object.html")
    return tmpl.render(title="Get Object Results", rows=rows)


def get_ticket_view(provides, all_app_runs, context) -> str:
    context["prerender"] = True
    rows = []
    for _summary, action_results in all_app_runs:
        for ar in action_results:
            for record in ar.get_data():
                row = {k.upper(): str(v) for k, v in record.items() if v is not None}
                if row:
                    rows.append(row)
    env = _get_renderer()
    tmpl = env.get_template("sf_get_ticket.html")
    return tmpl.render(title="Get Ticket Results", rows=rows)
