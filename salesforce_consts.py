# File: salesforce_consts.py
# Copyright (c) 2017-2020 Splunk Inc.
#
# SPLUNK CONFIDENTIAL - Use or disclosure of this material in whole or in part
# without a valid written license from Splunk Inc. is PROHIBITED.
# --

PHANTOM_SYS_INFO_URL = "{url}rest/system_info"
PHANTOM_ASSET_INFO_URL = "{url}rest/asset/{asset_id}"


URL_GET_CODE = 'https://login.salesforce.com/services/oauth2/authorize'
URL_GET_TOKEN = 'https://login.salesforce.com/services/oauth2/token'

URL_GET_CODE_TEST = 'https://test.salesforce.com/services/oauth2/authorize'
URL_GET_TOKEN_TEST = 'https://test.salesforce.com/services/oauth2/token'


API_ENDPOINT_DESCRIBE_GLOBAL = '{version}/sobjects/'
API_ENDPOINT_GET_UPDATED = '{version}/sobjects/{sobject}/updated/'
API_ENDPOINT_OBJECT_ID = '{version}/sobjects/{sobject}/{id}/'
API_ENDPOINT_RUN_QUERY = '{version}/{query_type}/'
API_ENDPOINT_OBJECT = '{version}/sobjects/{sobject}/'
API_ENDPOINT_GET_LISTVIEWS = '{version}/sobjects/{sobject}/listviews/'
API_ENDPOINT_GET_LISTVIEW_LOCATOR = '{version}/sobjects/{sobject}/listviews/{locator}/'
API_ENDPOINT_BATCH_REQUEST = '{version}/composite/batch/'

CASE_FIELD_MAP = {
    'parent_case_id': 'ParentId',
    'subject': 'Subject',
    'priority': 'Priority',
    'description': 'Description',
    'status': 'Status',
    'closed': 'IsClosed',
    'escalated': 'IsEscalated'
}
SALESFORCE_INVALID_INTEGER = 'Please provide non-zero positive integer in "{parameter}"'
SALESFORCE_UNKNOWN_ERR_MSG = "Unknown error occurred. Please check the asset configuration and|or action parameters."
SALESFORCE_ERR_CODE_UNAVAILABLE = "Error code unavailable"
SALESFORCE_UNICODE_DAMMIT_TYPE_ERROR_MESSAGE = "Error occurred while connecting to the Salesforce server. Please check the asset configuration and|or the action parameters."
