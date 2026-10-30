**Unreleased**

* Migrated the connector to Splunk SOAR SDK 7.0.3 and updated the minimum supported Splunk SOAR version to 7.0.0.
* Updated supported Python versions to 3.13 and 3.14.
* Added the **make request** action for authenticated Salesforce REST API requests. TLS certificate verification is enabled by default.
* Reimplemented the existing browser OAuth with PKCE, Client Credentials, and legacy username-password authentication flows using SDK-native authentication clients.
* Added SDK-native health-check and OAuth callback REST handlers.
* Added lazy, non-destructive migration of legacy browser OAuth refresh tokens, cached API versions, polling offsets, and container source-data-identifier salts into SDK state partitions.
* **Browser OAuth upgrade action:** Existing browser OAuth assets reuse the migrated legacy refresh token and do not require immediate reauthorization while that token remains valid. Before the next Test Connectivity or reauthorization, update the Salesforce Connected App callback URL from the legacy `/rest/handler/.../<asset_name>/start_oauth` URL to the SDK webhook URL shown by the asset: `/webhook/<directory>/<asset_id>/start_oauth`.
