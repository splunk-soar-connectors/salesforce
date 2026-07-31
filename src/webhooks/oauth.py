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
from soar_sdk.auth import create_oauth_callback_handler

from ..auth import get_oauth_client


OAUTH_CALLBACK_ROUTE = "/start_oauth"

oauth_callback = create_oauth_callback_handler(
    get_oauth_client,
    success_message="Authorization successful! You can now close this tab.",
)


def register_oauth_webhook(app: App) -> App:
    app.webhook(OAUTH_CALLBACK_ROUTE, allowed_methods=["GET"])(oauth_callback)
    return app
