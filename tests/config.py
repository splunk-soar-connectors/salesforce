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
import os
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
REQUIRED_ENV_KEYS = ("client_id", "client_secret", "domain_url")


class RedactedTestConfig(dict[str, str]):
    def __repr__(self) -> str:
        return f"{type(self).__name__}(<redacted>)"


def load_test_config() -> RedactedTestConfig:
    """Load and validate the complete Salesforce live-test configuration."""
    load_dotenv(ENV_FILE, override=False)
    missing = [name for name in REQUIRED_ENV_KEYS if not os.environ.get(name)]
    if missing:
        raise AssertionError(
            "Missing required live test environment variables: " + ", ".join(missing)
        )

    return RedactedTestConfig(
        {
            name: os.environ[name]
            for name in (*REQUIRED_ENV_KEYS, "SOAR_ASSET_ID")
            if name in os.environ
        }
    )
