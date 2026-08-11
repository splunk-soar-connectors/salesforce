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
from collections.abc import Iterator
from soar_sdk.abstract import SOARClient
from soar_sdk.app import App
from soar_sdk.params import Param, Params, OnPollParams
from soar_sdk.action_results import ActionOutput, OutputField
from soar_sdk.logging import getLogger
from soar_sdk.models.container import Container
from soar_sdk.models.artifact import Artifact

from .asset import Asset
from .actions import register_actions
from .test_connectivity import run_test_connectivity
from .webhooks import OAUTH_CALLBACK_ROUTE, register_webhooks

logger = getLogger()


def create_salesforce_connector_app() -> App:
    app = App(
        name="Salesforce",
        app_type="ticketing",
        logo="logo_salesforce.svg",
        logo_dark="logo_salesforce_dark.svg",
        product_vendor="Salesforce",
        product_name="Salesforce",
        publisher="Splunk",
        appid="6c1316b0-88a7-4864-b684-3170f6c455be",
        fips_compliant=True,
        encrypt_cache_state=True,
        encrypt_ingest_state=True,
        asset_cls=Asset,
    )

    register_webhooks(app)

    @app.test_connectivity()
    def test_connectivity(soar: SOARClient, asset: Asset) -> None:
        run_test_connectivity(
            asset,
            oauth_callback_url=app.get_webhook_url(OAUTH_CALLBACK_ROUTE),
        )

    app = register_actions(app)

    return app


app = create_salesforce_connector_app()


@app.on_poll()
def on_poll(
    soar: SOARClient, asset: Asset, params: OnPollParams
) -> Iterator[Container | Artifact]:
    raise NotImplementedError()


class PostChatterParams(Params):
    id: str = Param(
        description="Object ID of the Case",
        primary=True,
        cef_types=["salesforce object id"],
    )
    title: str | None = Param(description="Title of the post")
    body: str = Param(description="Body of the post")


class PostChatterOutput(ActionOutput):
    id: str = OutputField(
        cef_types=["salesforce object id"], example_values=["0D51I00000Jw1tnSAB"]
    )
    success: bool


@app.action(  # type: ignore[arg-type]
    description="Post on the Chatter feed for a specified case",
    action_type="generic",
    read_only=False,
)
def post_chatter(
    params: PostChatterParams, soar: SOARClient, asset: Asset
) -> PostChatterOutput:
    raise NotImplementedError()


if __name__ == "__main__":
    app.cli()
