**Unreleased**

* Migrated the connector to the Splunk SOAR SDK and updated the minimum supported Splunk SOAR version to 7.0.0.
* Updated supported Python versions to 3.13 and 3.14.
* Added the **make request** action for authenticated Salesforce REST API requests. TLS certificate verification is enabled by default.
* Reimplemented the existing browser OAuth with PKCE, Client Credentials, and legacy username-password authentication flows using SDK-native authentication clients.
* Added SDK-native health-check and OAuth callback REST handlers.
* Added migration support for legacy polling offsets and container source-data-identifier salts.
