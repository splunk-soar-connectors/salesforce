# --
# File: salesforce_consts.py
#
# Copyright (c) Phantom Cyber Corporation, 2017-2018
#
# This unpublished material is proprietary to Phantom Cyber.
# All rights reserved. The methods and
# techniques described herein are considered trade secrets
# and/or confidential. Reproduction or distribution, in whole
# or in part, is forbidden except by express written permission
# of Phantom Cyber.
#
# --

PHANTOM_SYS_INFO_URL = "https://127.0.0.1/rest/system_info"
PHANTOM_ASSET_INFO_URL = "https://127.0.0.1/rest/asset/{asset_id}"


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
