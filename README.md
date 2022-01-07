[comment]: # "Auto-generated SOAR connector documentation"
# Salesforce

Publisher: Splunk  
Connector Version: 2\.0\.19  
Product Vendor: Salesforce  
Product Name: Salesforce  
Product Version Supported (regex): "\.\*"  
Minimum Product Version: 4\.10\.0\.40961  

This app implements actions to manage objects on Salesforce

[comment]: # " File: readme.md"
[comment]: # "  Copyright (c) 2017-2021 Splunk Inc."
[comment]: # ""
[comment]: # "Licensed under the Apache License, Version 2.0 (the 'License');"
[comment]: # "you may not use this file except in compliance with the License."
[comment]: # "You may obtain a copy of the License at"
[comment]: # ""
[comment]: # "    http://www.apache.org/licenses/LICENSE-2.0"
[comment]: # ""
[comment]: # "Unless required by applicable law or agreed to in writing, software distributed under"
[comment]: # "the License is distributed on an 'AS IS' BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,"
[comment]: # "either express or implied. See the License for the specific language governing permissions"
[comment]: # "and limitations under the License."
[comment]: # ""
## Authentication

To pass test connectivity, you need to configure an app on Salesforce. To do so, navigate to
<https://www.salesforce.com/> in a browser and navigate to the login page. Log in with a Salesforce
account.

1.  In the drop-down list of the account (in the upper-right corner), select **Setup**
2.  Go to **Apps** , then **App Manager** and click on **New Connected App**
3.  On the New Connected App page, fill the following required fields under Basic Information:
    -   Connected App Name. For example, Salesforce Phantom App
    -   API name. For example, Salesforce Phantom App
    -   Contact Email. For example, xyz@xyz.com
4.  Go to API (Enable OAuth Settings), and select Enable OAuth Settings. Fill it out as mention in
    the below image or else follow these steps
    -   Under the **Callback URL** , we will be updating the entry of https://phantom.local to
        reflect the actual redirect URI. We will get this while we create Phantom App's asset in the
        below section titled "Configure the Salesforce Phantom app's Asset"

    -   Under **Selected OAuth Scopes field** add the following two scopes from **Available OAuth
        Scopes**
        -   Access and manage your data(api)
        -   Perform requests on your behalf at any time(refresh_token,ofline_access)

    -   Select the **Require Secret for Web Server Flow** checkbox

          
        [![](img/app_config.png)](img/app_config.png)
5.  Click on **Save**

## Configure the Salesforce Phantom app's Asset

When creating an asset for the **Salesforce** app, place the **Consumer Key** of the app created
during the previous step in the **Client ID** field and place the **Consumer Secret** generated
during the app creation process in the **Client Secret** field. Then, click **SAVE** .  
  
After saving, a new field will appear in the **Asset Settings** tab. Take the URL found in the
**POST incoming for Salesforce to this location** field. To this URL, add **/start_oauth** . After
doing so the URL should look something like:  

https://\<phantom_host>/rest/handler/salesforce_6c1316b0-88a7-4864-b684-3170f6c455be/\<asset_name>/start_oauth

[![](img/asset_config.png)](img/asset_config.png)  
  

Click **Edit** on the app created in a previous step and place it in the **Callback URL** field.

Once again, click on Save.

## Method to Run Test Connectivity with Oauth

After setting up the asset, click the **TEST CONNECTIVITY** button. A window should pop up and
display a URL as shown in the below image. Navigate to this URL in a separate browser tab. This new
tab will redirect to a Salesforce login page. Log in to a Salesforce account. Finally, close that
tab when instructed to do. The test connectivity window should show a success. **The app should now
be ready to use.**

  
[![](img/modal.png)](img/modal.png)  
  

## Method to Run Test Connectivity with Username and Password

If you optionally specify username and password in the asset configuration, test connectivity will
work differently; the main difference being that when you launch the test connectivity, there is no
need to log into the Salesforce instance to authorize the app.

**Note:** The password field should be composed of your password with your account's security token
appended at the end. Example: MyPasswordMyToken (this is not the same as the **client_secret** )

## Test Environment

You may want to configure an asset to work with a Salesforce test environment. This is the case if
the login URL for that Salesforce instance is <https://test.salesforce.com> as opposed to
<https://login.salesforce.com> . In this case, you should check the appropriate box in the asset
configuration.

## Ingestion

### Common points for scheduled interval polling and manual polling

-   The parameters of the On Poll action ignored in this application are start_time, end_time,
    container_id, artifact_count.

-   The data will be fetched based on the value specified in the configuration parameters 'Poll for
    this Salesforce Object'(default value is Case if not specified) and 'Poll this List View'
    parameter. To ingest objects, a ListView should be specified.

-   The created artifact's CEF fields will be the same names as the fields in the Object in
    Salesforce. You may want to map these to standard CEF fields. This can be done by providing a
    JSON that describes the mapping. For example, if the Salesforce object has the field
    **ip_address\_\_c** , and you want this to be **sourceAddress** , the following file would be
    appropriate.

    ``` shell
                    
                    {
                        "ip_address__c": "sourceAddress"
                    }
                    
                    
    ```

### 'Include view data in artifact' Configuration Parameter

-   This configuration parameter can be used to prevent the creation of duplicate artifacts.
-   If disabled, the on poll will ignore the value of "LastViewedDate" and "LastReferencedDate"
    during artifact creation.
-   If enabled, the on poll will include the value of "LastViewedDate" and "LastReferencedDate"
    during artifact creation.
-   Case is an example of an object in which both the values (LastViewedDate and LastReferencedDate)
    are present.

### Scheduled \| Interval polling

-   During scheduled \| interval polling, the app will start from the first object and will ingest
    up to the number of objects specified in the 'Get this many results on first ingestion'(Default
    value 10) parameter. Then it remembers the last object's offset Id and stores it in the state
    file against the key 'cur_offset'. The next scheduled ingestion will start from the offset Id in
    the state file and will ingest all the remaining objects of defined ListView.

### Manual polling

-   During manual polling, the app will start from the first object and will ingest up to the number
    of objects specified in the 'Maximum containers' parameter.

## Note

-   Currently, the **List Objects** , the **List Tickets** , and the **On Poll** actions can fetch a
    maximum of 4000 records.
-   The maximum offset value supported by the Salesforce API is 2000, as mentioned in this
    [**documentation**
    .](https://developer.salesforce.com/docs/atlas.en-us.soql_sosl.meta/soql_sosl/sforce_api_calls_soql_select_offset.htm)
-   If this issue gets resolved with the Salesforce API, then the mentioned actions will be able to
    fetch all of the records.


### Configuration Variables
The below configuration variables are required for this Connector to operate.  These variables are specified when configuring a Salesforce asset in SOAR.

VARIABLE | REQUIRED | TYPE | DESCRIPTION
-------- | -------- | ---- | -----------
**client\_id** |  required  | string | Client ID
**client\_secret** |  required  | password | Client Secret
**username** |  optional  | string | Username
**password** |  optional  | password | Password
**is\_test\_environment** |  optional  | boolean | Use a Salesforce test environment
**poll\_sobject** |  optional  | string | Poll for this Salesforce Object
**poll\_view\_name** |  optional  | string | Poll this List View
**first\_ingestion\_max** |  optional  | numeric | Get this many results on first ingestion
**cef\_name\_map** |  optional  | file | Mapping of Salesforce to CEF fields
**last\_view\_date** |  optional  | boolean | Include view date in artifact

### Supported Actions  
[test connectivity](#action-test-connectivity) - Validate connection using the configured credentials  
[run query](#action-run-query) - Run a query using the Salesforce Object Query Language \(SOQL\)  
[create object](#action-create-object) - Create a new Salesforce object  
[create ticket](#action-create-ticket) - Create a new Case  
[delete object](#action-delete-object) - Delete an object  
[delete ticket](#action-delete-ticket) - Delete a Case  
[update object](#action-update-object) - Update an object  
[update ticket](#action-update-ticket) - Update a Case  
[list objects](#action-list-objects) - Get a list of objects  
[list tickets](#action-list-tickets) - Get a list of Cases  
[get object](#action-get-object) - Get info about a Salesforce object  
[get ticket](#action-get-ticket) - Get info about a Case  
[post chatter](#action-post-chatter) - Post on the Chatter feed for a specified case  
[on poll](#action-on-poll) - Poll for new Objects on Salesforce  

## action: 'test connectivity'
Validate connection using the configured credentials

Type: **test**  
Read only: **True**

#### Action Parameters
No parameters are required for this action

#### Action Output
No Output  

## action: 'run query'
Run a query using the Salesforce Object Query Language \(SOQL\)

Type: **investigate**  
Read only: **True**

To run a query that includes a wildcard character, use <code>%25</code> instead of <code>%</code>\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**query** |  required  | SOQL Query | string | 
**endpoint** |  required  | Which Query endpoint to use | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.endpoint | string | 
action\_result\.parameter\.query | string | 
action\_result\.data\.\*\.records\.\* | string | 
action\_result\.summary\.num\_objects | numeric | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'create object'
Create a new Salesforce object

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sobject** |  required  | Name of object | string |  `salesforce object name` 
**field\_values** |  required  | JSON Object of Key\-Value pairs to update | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.field\_values | string | 
action\_result\.parameter\.sobject | string |  `salesforce object name` 
action\_result\.data\.\*\.id | string |  `salesforce object id` 
action\_result\.data\.\*\.success | boolean | 
action\_result\.summary\.obj\_id | string |  `salesforce object id` 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'create ticket'
Create a new Case

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**parent\_case\_id** |  optional  | Object ID of Parent Case | string |  `salesforce object id` 
**subject** |  optional  | Subject | string | 
**priority** |  optional  | Priority | string | 
**description** |  optional  | Description | string | 
**field\_values** |  optional  | JSON Object of Key\-Value pairs to update | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.description | string | 
action\_result\.parameter\.field\_values | string | 
action\_result\.parameter\.parent\_case\_id | string |  `salesforce object id` 
action\_result\.parameter\.priority | string | 
action\_result\.parameter\.subject | string | 
action\_result\.data\.\*\.id | string |  `salesforce object id` 
action\_result\.data\.\*\.success | boolean | 
action\_result\.summary\.obj\_id | string |  `salesforce object id` 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'delete object'
Delete an object

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sobject** |  required  | Name of object | string |  `salesforce object name` 
**id** |  required  | Salesforce Object ID | string |  `salesforce object id` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.parameter\.sobject | string |  `salesforce object name` 
action\_result\.data | string | 
action\_result\.summary | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'delete ticket'
Delete a Case

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** |  required  | Object ID of the Case | string |  `salesforce object id` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.data | string | 
action\_result\.summary | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'update object'
Update an object

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sobject** |  required  | Name of object | string |  `salesforce object name` 
**id** |  required  | Salesforce Object ID | string |  `salesforce object id` 
**field\_values** |  optional  | JSON Object of Key\-Value pairs to update | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.field\_values | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.parameter\.sobject | string |  `salesforce object name` 
action\_result\.data | string | 
action\_result\.summary\.obj\_id | string |  `salesforce object id` 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'update ticket'
Update a Case

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** |  required  | Object ID of the Case | string |  `salesforce object id` 
**parent\_case\_id** |  optional  | Object ID of Parent Case | string |  `salesforce object id` 
**subject** |  optional  | Subject | string | 
**priority** |  optional  | Priority | string | 
**description** |  optional  | Description | string | 
**status** |  optional  | Status | string | 
**field\_values** |  optional  | JSON Object of Key\-Value pairs to update | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.description | string | 
action\_result\.parameter\.field\_values | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.parameter\.parent\_case\_id | string |  `salesforce object id` 
action\_result\.parameter\.priority | string | 
action\_result\.parameter\.status | string | 
action\_result\.parameter\.subject | string | 
action\_result\.data | string | 
action\_result\.summary\.obj\_id | string |  `salesforce object id` 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'list objects'
Get a list of objects

Type: **investigate**  
Read only: **True**

To get a list of objects, you must specify the name of a list view\. By leaving the <b>view\_name</b> blank, this action will instead return a list of valid names in the summary\. Also, this action will only work if the specified object has a list view\. If it does not, you could use the <b>run query</b> action instead\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sobject** |  required  | Name of object | string |  `salesforce object name` 
**view\_name** |  optional  | Unique name of a list view | string |  `salesforce listview name` 
**limit** |  optional  | Paging limit | numeric | 
**offset** |  optional  | Paging offset | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.limit | numeric | 
action\_result\.parameter\.offset | numeric | 
action\_result\.parameter\.sobject | string |  `salesforce object name` 
action\_result\.parameter\.view\_name | string |  `salesforce listview name` 
action\_result\.data\.\* | string | 
action\_result\.data\.\*\.columns\.Id\.value | string |  `salesforce object id` 
action\_result\.summary\.num\_objects | numeric | 
action\_result\.summary\.view\_names | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'list tickets'
Get a list of Cases

Type: **investigate**  
Read only: **True**

To get a list of objects, you must specify the name of a list view\. By leaving the <b>view\_name</b> blank, this action will instead return a list of valid names in the summary\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**view\_name** |  optional  | Unique name of a list view | string |  `salesforce listview name` 
**limit** |  optional  | Paging limit | numeric | 
**offset** |  optional  | Paging offset | numeric | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.limit | numeric | 
action\_result\.parameter\.offset | numeric | 
action\_result\.parameter\.view\_name | string |  `salesforce listview name` 
action\_result\.data\.\*\.columns\.CaseNumber\.value | string | 
action\_result\.data\.\*\.columns\.ContactId\.value | string |  `salesforce object id` 
action\_result\.data\.\*\.columns\.Contact\_Id\.value | string |  `salesforce object id` 
action\_result\.data\.\*\.columns\.Contact\_Name\.value | string | 
action\_result\.data\.\*\.columns\.CreatedDate\.value | string | 
action\_result\.data\.\*\.columns\.Id\.value | string |  `salesforce object id` 
action\_result\.data\.\*\.columns\.LastModifiedDate\.value | string | 
action\_result\.data\.\*\.columns\.OwnerId\.value | string |  `salesforce object id` 
action\_result\.data\.\*\.columns\.Owner\_Id\.value | string |  `salesforce object id` 
action\_result\.data\.\*\.columns\.Owner\_NameOrAlias\.value | string | 
action\_result\.data\.\*\.columns\.Priority\.value | string | 
action\_result\.data\.\*\.columns\.RecordTypeId\.value | string | 
action\_result\.data\.\*\.columns\.Status\.value | string | 
action\_result\.data\.\*\.columns\.Subject\.value | string | 
action\_result\.data\.\*\.columns\.SystemModstamp\.value | string | 
action\_result\.summary\.num\_objects | numeric | 
action\_result\.summary\.view\_names | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'get object'
Get info about a Salesforce object

Type: **investigate**  
Read only: **True**

If you have custom fields added to an object, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**sobject** |  required  | Name of object | string |  `salesforce object name` 
**id** |  required  | Salesforce Object ID | string |  `salesforce object id` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.parameter\.sobject | string |  `salesforce object name` 
action\_result\.data\.\* | string | 
action\_result\.data\.\*\.id | string |  `salesforce object id` 
action\_result\.summary | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'get ticket'
Get info about a Case

Type: **investigate**  
Read only: **True**

If you have custom fields added to a Case, then they might not show up in the playbook editor, so you will need to manually type the datapath to use it\.

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** |  required  | Object ID of the Case | string |  `salesforce object id` 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.data\.\*\.AccountId | string |  `salesforce object id` 
action\_result\.data\.\*\.AssetId | string | 
action\_result\.data\.\*\.CaseNumber | string | 
action\_result\.data\.\*\.Case\_Open\_minutes\_\_c | numeric | 
action\_result\.data\.\*\.ClosedDate | string | 
action\_result\.data\.\*\.Closed\_Time\_Days\_\_c | string | 
action\_result\.data\.\*\.ContactEmail | string | 
action\_result\.data\.\*\.ContactFax | string | 
action\_result\.data\.\*\.ContactId | string |  `salesforce object id` 
action\_result\.data\.\*\.ContactMobile | string | 
action\_result\.data\.\*\.ContactPhone | string | 
action\_result\.data\.\*\.CreatedById | string |  `salesforce object id` 
action\_result\.data\.\*\.CreatedDate | string | 
action\_result\.data\.\*\.Customer\_Impacting\_\_c | string | 
action\_result\.data\.\*\.Date\_Reviewed\_\_c | string | 
action\_result\.data\.\*\.Days\_Open\_\_c | numeric | 
action\_result\.data\.\*\.Description | string | 
action\_result\.data\.\*\.Discovery\_Method\_\_c | string | 
action\_result\.data\.\*\.Discovery\_Time\_Hours\_\_c | string | 
action\_result\.data\.\*\.EngineeringReqNumber\_\_c | string | 
action\_result\.data\.\*\.Executive\_Summary\_\_c | string | 
action\_result\.data\.\*\.Id | string |  `salesforce object id` 
action\_result\.data\.\*\.Impact\_Summary\_\_c | string | 
action\_result\.data\.\*\.Impacted\_Environment\_\_c | string | 
action\_result\.data\.\*\.Incident\_Category\_\_c | string | 
action\_result\.data\.\*\.Incident\_Date\_\_c | string | 
action\_result\.data\.\*\.Incident\_Root\_Cause\_\_c | string | 
action\_result\.data\.\*\.Incident\_Sensitivity\_\_c | string | 
action\_result\.data\.\*\.Incident\_Severity\_\_c | string | 
action\_result\.data\.\*\.Incident\_Type\_\_c | string | 
action\_result\.data\.\*\.Investigation\_Category\_\_c | string | 
action\_result\.data\.\*\.Investigation\_Date\_\_c | string | 
action\_result\.data\.\*\.Investigation\_Summary\_\_c | string | 
action\_result\.data\.\*\.Investigation\_Type\_\_c | string | 
action\_result\.data\.\*\.IsClosed | boolean | 
action\_result\.data\.\*\.IsDeleted | boolean | 
action\_result\.data\.\*\.IsEscalated | boolean | 
action\_result\.data\.\*\.LastModifiedById | string |  `salesforce object id` 
action\_result\.data\.\*\.LastModifiedDate | string | 
action\_result\.data\.\*\.LastReferencedDate | string | 
action\_result\.data\.\*\.LastViewedDate | string | 
action\_result\.data\.\*\.Origin | string | 
action\_result\.data\.\*\.OwnerId | string |  `salesforce object id` 
action\_result\.data\.\*\.ParentId | string |  `salesforce object id` 
action\_result\.data\.\*\.PotentialLiability\_\_c | string | 
action\_result\.data\.\*\.Priority | string | 
action\_result\.data\.\*\.Product\_\_c | string | 
action\_result\.data\.\*\.Reason | string | 
action\_result\.data\.\*\.RecordTypeId | string | 
action\_result\.data\.\*\.Resolution\_Date\_\_c | string | 
action\_result\.data\.\*\.Resolution\_Time\_Hours\_\_c | string | 
action\_result\.data\.\*\.Response\_Time\_Hours\_\_c | string | 
action\_result\.data\.\*\.Response\_Time\_Minutes\_\_c | numeric | 
action\_result\.data\.\*\.SITrack\_Response\_Task\_\_c | string | 
action\_result\.data\.\*\.SITracker\_Handoff\_Notes\_\_c | string | 
action\_result\.data\.\*\.SITracker\_Include\_in\_Handoff\_\_c | boolean | 
action\_result\.data\.\*\.SLAViolation\_\_c | string | 
action\_result\.data\.\*\.Status | string | 
action\_result\.data\.\*\.Subject | string | 
action\_result\.data\.\*\.SuppliedCompany | string | 
action\_result\.data\.\*\.SuppliedEmail | string | 
action\_result\.data\.\*\.SuppliedName | string | 
action\_result\.data\.\*\.SuppliedPhone | string | 
action\_result\.data\.\*\.SystemModstamp | string | 
action\_result\.data\.\*\.Type | string | 
action\_result\.data\.\*\.attributes\.type | string | 
action\_result\.data\.\*\.attributes\.url | string | 
action\_result\.summary | string | 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'post chatter'
Post on the Chatter feed for a specified case

Type: **generic**  
Read only: **False**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**id** |  required  | Object ID of the Case | string |  `salesforce object id` 
**title** |  optional  | Title of the post | string | 
**body** |  required  | Body of the post | string | 

#### Action Output
DATA PATH | TYPE | CONTAINS
--------- | ---- | --------
action\_result\.status | string | 
action\_result\.parameter\.body | string | 
action\_result\.parameter\.id | string |  `salesforce object id` 
action\_result\.parameter\.title | string | 
action\_result\.data\.\*\.id | string |  `salesforce object id` 
action\_result\.data\.\*\.success | boolean | 
action\_result\.summary\.obj\_id | string |  `salesforce object id` 
action\_result\.message | string | 
summary\.total\_objects | numeric | 
summary\.total\_objects\_successful | numeric |   

## action: 'on poll'
Poll for new Objects on Salesforce

Type: **ingest**  
Read only: **True**

#### Action Parameters
PARAMETER | REQUIRED | DESCRIPTION | TYPE | CONTAINS
--------- | -------- | ----------- | ---- | --------
**start\_time** |  optional  | Parameter Ignored in this app | numeric | 
**end\_time** |  optional  | Parameter Ignored in this app | numeric | 
**container\_id** |  optional  | Parameter Ignored in this app | numeric | 
**container\_count** |  required  | Maximum number of objects to ingest | numeric | 
**artifact\_count** |  optional  | Parameter Ignored in this app | numeric | 

#### Action Output
No Output