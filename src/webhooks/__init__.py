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

from .health import health_check
from .oauth import OAUTH_CALLBACK_ROUTE, oauth_callback


HEALTH_ROUTE = "health"


def register_webhooks(app: App) -> App:
    app.enable_webhooks(default_requires_auth=False)
    app.webhook(HEALTH_ROUTE, allowed_methods=["GET"])(health_check)
    app.webhook(OAUTH_CALLBACK_ROUTE, allowed_methods=["GET"])(oauth_callback)
    return app


__all__ = ["OAUTH_CALLBACK_ROUTE", "register_webhooks"]
