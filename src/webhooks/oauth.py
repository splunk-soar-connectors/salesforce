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
from soar_sdk.auth import create_oauth_callback_handler
from soar_sdk.webhooks.models import WebhookRequest, WebhookResponse

from ..auth import get_oauth_client


OAUTH_CALLBACK_ROUTE = "start_oauth"
AUTHORIZATION_ERROR_STATE_KEY = "authorization_error"
MAX_AUTHORIZATION_ERROR_LENGTH = 1_000

sdk_oauth_callback = create_oauth_callback_handler(
    get_oauth_client,
    success_message="Authorization successful! You can now close this tab.",
)


def _first_query_value(request: WebhookRequest, name: str) -> str:
    values = request.query.get(name, [])
    return values[0] if values else ""


def oauth_callback(request: WebhookRequest) -> WebhookResponse:
    if error := _first_query_value(request, "error"):
        message = f"Salesforce authorization failed: {error}"
        if description := _first_query_value(request, "error_description"):
            message = f"{message}. {description}"
        sanitized_message = " ".join(message.split())
        request.asset.auth_state[AUTHORIZATION_ERROR_STATE_KEY] = sanitized_message[
            :MAX_AUTHORIZATION_ERROR_LENGTH
        ]

    return sdk_oauth_callback(request)
