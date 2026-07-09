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

from .. import views
from .create_object import create_object
from .create_ticket import create_ticket
from .delete_object import delete_object
from .delete_ticket import delete_ticket
from .get_object import get_object
from .get_ticket import get_ticket
from .list_objects import list_objects
from .list_tickets import list_tickets
from .make_request import make_request
from .post_chatter import post_chatter
from .run_query import run_query
from .update_object import update_object
from .update_ticket import update_ticket


def register_actions(app: App) -> App:
    app.make_request()(make_request)

    app.register_action(
        action=create_object,
        description="Create a new Salesforce object",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=create_ticket,
        description="Create a new Case",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=delete_object,
        description="Delete an object",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=delete_ticket,
        description="Delete a Case",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=get_object,
        description="Get info about a Salesforce object",
        action_type="investigate",
        verbose="If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
        view_handler=views.get_object_view,
    )
    app.register_action(
        action=get_ticket,
        description="Get info about a Case",
        action_type="investigate",
        verbose="If you have custom fields added to a Case, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it.",
        view_handler=views.get_ticket_view,
    )
    app.register_action(
        action=list_objects,
        description="Get a list of objects",
        action_type="investigate",
        verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary. Also, this action will only work if the specified object has a list view. If it does not, you could use the <b>run query</b> action instead.",
        view_handler=views.list_objects_view,
    )
    app.register_action(
        action=list_tickets,
        description="Get a list of Cases",
        action_type="investigate",
        verbose="To get a list of objects, you must specify the name of a list view. By leaving the <b>view_name</b> blank, this action will instead return a list of valid names in the summary.",
    )
    app.register_action(
        action=post_chatter,
        description="Post on the Chatter feed for a specified case",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=run_query,
        description="Run a query using the Salesforce Object Query Language (SOQL)",
        action_type="investigate",
        verbose="To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>.",
        view_handler=views.run_query_view,
    )
    app.register_action(
        action=update_object,
        description="Update an object",
        action_type="generic",
        read_only=False,
    )
    app.register_action(
        action=update_ticket,
        description="Update a Case",
        action_type="generic",
        read_only=False,
    )

    return app
