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
from soar_sdk.app import App

from .get_object import get_object
from .run_query import run_query


def register_actions(app: App) -> App:
    """
    Registers actions to salesforce app and returns it.

    Args:
        app (App): app to register actions on.

    Returns:
        App: app with registered salesforce actions.
    """

    app.register_action(
        action=get_object,  # type: ignore[arg-type]
        description="Get info about a Salesforce object",
        action_type="investigate",
        verbose="If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
        render_as="table",
    )

    app.register_action(
        action=run_query,  # type: ignore[arg-type]
        description="Run a query using the Salesforce Object Query Language (SOQL)",
        action_type="investigate",
        verbose="To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>.",
    )

    return app
