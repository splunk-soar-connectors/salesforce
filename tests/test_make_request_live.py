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
import json
from inspect import unwrap
from uuid import uuid4

import pytest
from soar_sdk.app import App
from soar_sdk.exceptions import ActionFailure

from src.actions.make_request import SalesforceMakeRequestParams, make_request
from src.asset import Asset
from src.test_connectivity import run_test_connectivity


@pytest.mark.live
def test_make_request_live(app: App, asset: Asset) -> None:
    assert (
        SalesforceMakeRequestParams(
            http_method="GET", endpoint="/sobjects/Case"
        ).verify_ssl
        is True
    )
    assert (
        SalesforceMakeRequestParams(
            http_method="GET", endpoint="/sobjects/Case", verify_ssl=False
        ).verify_ssl
        is False
    )

    run_test_connectivity(asset)
    action = unwrap(make_request)

    for endpoint in ("/sobjects/Case/describe", "sobjects/Case/describe"):
        result = action(
            SalesforceMakeRequestParams(
                http_method="GET",
                endpoint=endpoint,
                headers='{"Accept": "application/json"}',
                timeout=60,
                verify_ssl=False,
            ),
            app.soar_client,
            asset,
        )
        assert result.status_code == 200
        assert json.loads(result.response_body)["name"] == "Case"

    json_query_result = action(
        SalesforceMakeRequestParams(
            http_method="GET",
            endpoint="/query",
            query_parameters='{"q": "SELECT Id FROM User LIMIT 1"}',
        ),
        app.soar_client,
        asset,
    )
    assert json_query_result.status_code == 200
    assert json.loads(json_query_result.response_body)["totalSize"] == 1

    raw_query_result = action(
        SalesforceMakeRequestParams(
            http_method="GET",
            endpoint="/query",
            query_parameters="?q=SELECT+Id+FROM+User+LIMIT+1",
        ),
        app.soar_client,
        asset,
    )
    assert raw_query_result.status_code == 200
    assert json.loads(raw_query_result.response_body)["totalSize"] == 1

    subject = f"SDK make request live test {uuid4()}"
    created_id: str | None = None
    try:
        create_result = action(
            SalesforceMakeRequestParams(
                http_method="POST",
                endpoint="/sobjects/Case",
                body=json.dumps({"Subject": subject, "Origin": "Web"}),
            ),
            app.soar_client,
            asset,
        )
        assert create_result.status_code == 201
        create_response = json.loads(create_result.response_body)
        assert create_response["success"] is True
        created_id = create_response["id"]
    finally:
        if created_id is not None:
            delete_result = action(
                SalesforceMakeRequestParams(
                    http_method="DELETE",
                    endpoint=f"/sobjects/Case/{created_id}",
                ),
                app.soar_client,
                asset,
            )
            assert delete_result.status_code == 204

    error_result = action(
        SalesforceMakeRequestParams(
            http_method="GET",
            endpoint="/query",
            query_parameters='{"q": "not valid SOQL"}',
        ),
        app.soar_client,
        asset,
    )
    assert error_result.status_code == 400
    assert "MALFORMED_QUERY" in error_result.response_body
    assert app.soar_client.get_message() == "Request completed with status 400"

    with pytest.raises(ActionFailure, match="Invalid JSON in headers:"):
        action(
            SalesforceMakeRequestParams(
                http_method="GET",
                endpoint="/sobjects/Case",
                headers="not-valid-json",
            ),
            app.soar_client,
            asset,
        )

    with pytest.raises(ActionFailure, match="Invalid JSON in body:"):
        action(
            SalesforceMakeRequestParams(
                http_method="POST",
                endpoint="/sobjects/Case",
                body="{not-valid-json",
            ),
            app.soar_client,
            asset,
        )
