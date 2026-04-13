## Authentication

Starting with Salesforce Spring '26, new Connected Apps can no longer be created by default.
Salesforce now requires new integrations to use **External Client Apps (ECA)**. This connector
supports External Client Apps using the OAuth 2.0 Web Server (authorization code) flow with PKCE
and refresh token rotation.

> **Note for existing Connected App users:** If you already have a Connected App configured and
> working, it will continue to function. Only new app creation is restricted. Follow the External
> Client App steps below for any new setup.

## Step 1: Create an External Client App in Salesforce

1. Navigate to <https://www.salesforce.com/> and log in with a Salesforce account.
1. In the account drop-down (upper-right corner), select **Setup**.
1. In the Quick Find box, search for **External Client Apps** and select **External Client App
   Manager**.
1. Click **New External Client App**.
1. Fill in the required fields under **Basic Information**:
   - **External Client App Name**: for example, `Salesforce Splunk SOAR App`
   - **API Name**: for example, `Salesforce_Splunk_SOAR_App`
   - **Contact Email**: for example, `xyz@xyz.com`
   - **Distribution State**: set to `Local`
1. Under **OAuth Settings**, click **Enable OAuth Settings** and configure the following:
   - **Callback URL**: Enter a placeholder for now (for example, `https://splunk_soar.local/start_oauth`).
     You will replace this with the real URL in Step 3 below.
   - **Selected OAuth Scopes**: Add the following two scopes from the **Available OAuth Scopes** list:
     - `Manage user data via APIs (api)`
     - `Perform requests at any time (refresh_token, offline_access)`
   - Enable **Require Proof Key for Code Exchange (PKCE) Extension for Supported Authorization Flows**
     (the connector now implements PKCE).
   - Enable **Require Secret for Web Server Flow**.
   - Enable **Require Secret for Refresh Token Flow**.
1. Click **Save**.
1. After saving, locate your app in External Client App Manager and note the following values:
   - **Consumer Key** — this maps to the **Client ID** field in the Splunk SOAR asset.
   - **Consumer Secret** — this maps to the **Client Secret** field in the Splunk SOAR asset.

## Step 2: Configure the Salesforce Splunk SOAR App Asset

1. In Splunk SOAR, open the **Apps** page and find the **Salesforce** app.

1. Click **Configure New Asset**.

1. In the **Asset Settings** tab, fill in:

   - **Client ID**: paste the **Consumer Key** from your External Client App.
   - **Client Secret**: paste the **Consumer Secret** from your External Client App.

1. Click **SAVE**.

1. After saving, a new field appears in the **Asset Settings** tab:
   **POST incoming for Salesforce to this location**. Copy that URL and append **/start_oauth** to it.
   The resulting URL will look like:

   `https://<splunk_soar_host>/rest/handler/salesforce_6c1316b0-88a7-4864-b684-3170f6c455be/<asset_name>/start_oauth`

## Step 3: Set the Callback URL in Your External Client App

1. Return to Salesforce Setup and open your External Client App.
1. Click **Edit** and replace the placeholder **Callback URL** with the `/start_oauth` URL you
   copied in Step 2.
1. Click **Save**.

## Method to Run Test Connectivity with OAuth

After completing the above setup, click the **TEST CONNECTIVITY** button in the Splunk SOAR asset.
A window will appear with a URL. Open that URL in a new browser tab. The tab will redirect to a
Salesforce login page. Log in with a Salesforce account and authorize the app. Close the tab when
instructed. The test connectivity window should show success. **The app is now ready to use.**

[![](img/modal.png)](img/modal.png)

> **Security note:** This connector uses PKCE (Proof Key for Code Exchange) to protect the
> authorization code flow and supports Salesforce refresh token rotation. If Salesforce issues a new
> refresh token during a session refresh, the connector automatically replaces the stored token so
> the integration remains active.

## Method to Run Test Connectivity with Username and Password (Legacy)

> **This flow is not recommended for new External Client App setups.** External Client Apps in
> Salesforce no longer support the resource owner password grant by default.

If you are using a legacy Connected App that still allows the username-password flow, you can
optionally specify a username and password in the asset configuration. When both are provided, test
connectivity will authenticate directly without requiring a browser login.

**Note:** The **Password** field must be your Salesforce password with your account's security
token appended at the end. Example: `MyPasswordMyToken` (this is not the same as the
**Client Secret**).

## Test Environment

If the login URL for your Salesforce instance is <https://test.salesforce.com> rather than
<https://login.salesforce.com>, enable the **Use a Salesforce test environment** checkbox in the
asset configuration before running test connectivity.

## Ingestion

### Common points for scheduled interval polling and manual polling

- The parameters of the On Poll action ignored in this application are start_time, end_time,
  container_id, artifact_count.

- The data will be fetched based on the value specified in the configuration parameters 'Poll for
  this Salesforce Object'(default value is Case if not specified) and 'Poll this List View'
  parameter. To ingest objects, a ListView should be specified.

- The created artifact's CEF fields will be the same names as the fields in the Object in
  Salesforce. You may want to map these to standard CEF fields. This can be done by providing a
  JSON that describes the mapping. For example, if the Salesforce object has the field
  **ip_address\_\_c** , and you want this to be **sourceAddress** , the following file would be
  appropriate.

  ```shell
                  
                  {
                      "ip_address__c": "sourceAddress"
                  }
                  
                  
  ```

### 'Include view data in artifact' Configuration Parameter

- This configuration parameter can be used to prevent the creation of duplicate artifacts.
- If disabled, the on poll will ignore the value of "LastViewedDate" and "LastReferencedDate"
  during artifact creation.
- If enabled, the on poll will include the value of "LastViewedDate" and "LastReferencedDate"
  during artifact creation.
- Case is an example of an object in which both the values (LastViewedDate and LastReferencedDate)
  are present.

### Scheduled | Interval polling

- During scheduled | interval polling, the app will start from the first object and will ingest
  up to the number of objects specified in the 'Get this many results on first ingestion'(Default
  value 10) parameter. Then it remembers the last object's offset Id and stores it in the state
  file against the key 'cur_offset'. The next scheduled ingestion will start from the offset Id in
  the state file and will ingest all the remaining objects of defined ListView.

### Manual polling

- During manual polling, the app will start from the first object and will ingest up to the number
  of objects specified in the 'Maximum containers' parameter.

## Note

- Currently, the **List Objects** , the **List Tickets** , and the **On Poll** actions can fetch a
  maximum of 4000 records. The maximum offset value supported by the Salesforce API is 2000, as
  mentioned in this [**documentation**
  .](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_select_offset.htm)
  If this issue gets resolved with the Salesforce API, then the mentioned actions will be able to
  fetch all of the records.
- The List of available standard objects can be found
  [here](https://developer.salesforce.com/docs/atlas.en-us.object_reference.meta/object_reference/sforce_api_objects_list.htm)
  .
- While using custom object's name as input parameter use "API Name" attribute of that object.
