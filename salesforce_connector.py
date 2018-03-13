# --
# File: salesforce_connector.py
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

# Phantom App imports
import phantom.app as phantom
from phantom.base_connector import BaseConnector
from phantom.action_result import ActionResult

# Usage of the consts file is recommended
from salesforce_consts import *

# import re
import os
import time
import json
import requests
import encryption_helper
from bs4 import BeautifulSoup
from django.http import HttpResponse
# from django.utils.dateparse import parse_datetime
# from datetime import datetime, timedelta
import hashlib


DT_FORMAT = '%Y-%m-%dT%H:%M:%S%z'


class RetVal(tuple):
    def __new__(cls, val1, val2=None):
        return tuple.__new__(RetVal, (val1, val2))


def _delete_app_state(asset_id, app_connector=None):
    dirpath = os.path.split(__file__)[0]
    state_file = "{0}/{1}_state.json".format(dirpath, asset_id)
    try:
        os.remove(state_file)
    except:
        pass

    return phantom.APP_SUCCESS


def _save_app_state(state, asset_id, app_connector=None):
    """ Saves the state into the same file """

    # get the directory of the file
    dirpath = os.path.split(__file__)[0]
    state_file = "{0}/{1}_state.json".format(dirpath, asset_id)

    if (app_connector):
        app_connector.debug_print("Saving state: ", state)

    try:
        with open(state_file, 'w+') as f:
            f.write(json.dumps(state))
    except Exception as e:
        print "Unable to save state file: {0}".format(str(e))
        pass

    return phantom.APP_SUCCESS


def _load_app_state(asset_id, app_connector=None):
    """ Loads the data that was added to """

    # get the directory of the file
    dirpath = os.path.split(__file__)[0]
    state_file = "{0}/{1}_state.json".format(dirpath, asset_id)

    state = {}

    try:
        with open(state_file, 'r') as f:
            in_json = f.read()
            state = json.loads(in_json)
    except Exception as e:
        if (app_connector):
            app_connector.debug_print("In _load_app_state: Exception: {0}".format(str(e)))
        pass

    if (app_connector):
        app_connector.debug_print("Loaded state: ", state)

    return state


def _return_error(msg, state, asset_id, status):
    state['error'] = True
    _save_app_state(state, asset_id)
    return HttpResponse(msg, status=status)


def _handle_oauth_start(request, path_parts):
    # This is where we should land AFTER the redirect callback when the user authenticates on Salesforce
    # After that, it will retrieve the "code" which is sent, and then use that to retrieve the refresh_token
    asset_id = request.GET.get('state')
    if (not asset_id):
        return HttpResponse("ERROR: Asset ID not found in URL")

    code = request.GET.get('code')
    if code:
        state = _load_app_state(asset_id)
        creds = state['creds']
        url_get_token = state['url_get_token']
        creds_dict = json.loads(encryption_helper.decrypt(creds, asset_id))  # pylint: disable=E1101
        params = creds_dict
        params.pop('response_type', None)
        params['grant_type'] = 'authorization_code'
        params['code'] = code
        try:
            r = requests.post(url_get_token, params=params)  # noqa
            resp_json = r.json()
        except Exception as e:
            return _return_error(
                "Error retrieving OAuth Token: {}. URL: {}".format(
                    str(e),
                    get_token_url
                ),
                state, asset_id, 401
            )
        refresh_token = resp_json.get('refresh_token')
        if not refresh_token:
            return _return_error(
                "Unable to retrieve refresh token. Maybe app scope is set incorrectly?",
                state, asset_id, 401
            )
        state['refresh_token'] = encryption_helper.encrypt(refresh_token, asset_id)  # pylint: disable=E1101
        _save_app_state(state, asset_id)
        return HttpResponse("You can now close this page")
    return _return_error(
        "Something went wrong during authentication",
        state, asset_id, 401
    )


def _handle_redirect(request, path_parts):
    asset_id = request.GET.get('asset_id')
    if (not asset_id):
        return HttpResponse("ERROR: Asset ID not found in URL")

    state = _load_app_state(asset_id)
    enc_url = state['url']
    dec_url = encryption_helper.decrypt(enc_url, asset_id)  # pylint: disable=E1101

    resp = HttpResponse(status=302)
    resp['location'] = dec_url
    return resp


def handle_request(request, path_parts):
    if len(path_parts) < 2:
        return {'error': True, 'message': 'Invalid REST endpoint request'}

    call_type = path_parts[1]

    if call_type == 'redirect':
        return _handle_redirect(request, path_parts)

    if call_type == 'start_oauth':
        return _handle_oauth_start(request, path_parts)

    return {'error': 'Invalid endpoint'}


def _get_dir_name_from_app_name(app_name):

    app_name = ''.join([x for x in app_name if x.isalnum()])
    app_name = app_name.lower()

    if (not app_name):
        # hardcode it
        app_name = "app_for_phantom"

    return app_name


class SalesforceConnector(BaseConnector):

    OAUTH_FLOW = 1
    USERNAME_PASSWORD = 2

    def __init__(self):

        # Call the BaseConnectors init first
        super(SalesforceConnector, self).__init__()

        self._state = None
        self._base_url = None
        self._oauth_token = None
        self._version_uri = None
        self._auth_flow = self.OAUTH_FLOW

    def _process_empty_reponse(self, response, action_result):

        if self.get_action_identifier() in ('update_ticket', 'update_object', 'delete_object', 'delete_ticket'):
            return RetVal(phantom.APP_SUCCESS, {})

        if response.status_code == 200:
            return RetVal(phantom.APP_SUCCESS, {})

        return RetVal(action_result.set_status(phantom.APP_ERROR, "Empty response and no information in the header"), None)

    def _process_html_response(self, response, action_result):

        # An html response, treat it like an error
        status_code = response.status_code

        try:
            soup = BeautifulSoup(response.text, "html.parser")
            error_text = soup.text
            split_lines = error_text.split('\n')
            split_lines = [x.strip() for x in split_lines if x.strip()]
            error_text = '\n'.join(split_lines)
        except:
            error_text = "Cannot parse error details"

        message = "Status Code: {0}. Data from server:\n{1}\n".format(status_code,
                error_text)

        message = message.replace('{', '{{').replace('}', '}}')

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):

        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to parse JSON response. Error: {0}".format(str(e))), None)

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        # You should process the error returned in the json
        message = "Error from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, r.text.replace('{', '{{').replace('}', '}}'))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_response(self, r, action_result):

        # store the r_text in debug data, it will get dumped in the logs if the action fails
        if hasattr(action_result, 'add_debug_data'):
            action_result.add_debug_data({'r_status_code': r.status_code})
            action_result.add_debug_data({'r_text': r.text})
            action_result.add_debug_data({'r_headers': r.headers})

        # Process each 'Content-Type' of response separately

        # Process a json response
        if 'json' in r.headers.get('Content-Type', ''):
            return self._process_json_response(r, action_result)

        if 'javascript' in r.headers.get('Content-Type', ''):
            return self._process_json_response(r, action_result)

        # Process an HTML resonse, Do this no matter what the api talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if 'html' in r.headers.get('Content-Type', ''):
            return self._process_html_response(r, action_result)

        # it's not content-type that is to be parsed, handle an empty response
        if not r.text:
            return self._process_empty_reponse(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, r.text.replace('{', '{{').replace('}', '}}'))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _make_rest_call(self, endpoint, action_result, headers=None, params=None, data=None, json=None, method="get", ignore_base_url=False, **kwargs):

        resp_json = None

        try:
            request_func = getattr(requests, method)
        except AttributeError:
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Invalid method: {0}".format(method)), resp_json)

        # Create a URL to connect to
        if ignore_base_url:
            url = endpoint
        else:
            if self._base_url is None:
                raise Exception("Base URL Is None")
            url = self._base_url + endpoint

        try:
            r = request_func(
                url,
                json=json,
                data=data,
                headers=headers,
                params=params,
                **kwargs
            )
        except Exception as e:
            return RetVal(action_result.set_status( phantom.APP_ERROR, "Error Connecting to server. Details: {0}".format(str(e))), resp_json)

        return self._process_response(r, action_result)

    def _retrieve_oauth_token(self, action_result):
        config = self.get_config()
        client_id = config['client_id']
        client_secret = config['client_secret']
        try:
            refresh_token = encryption_helper.decrypt(self._state['refresh_token'], self.get_asset_id())  # pylint: disable=E1101
        except KeyError:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error getting refresh token, has test connectivity been run?"
            )
        except Exception as e:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error decrypting refresh token", e
            )

        body = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': client_id,
            'client_secret': client_secret,
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        if config.get('is_test_environment'):
            url_get_token = URL_GET_TOKEN_TEST
        else:
            url_get_token = URL_GET_TOKEN

        ret_val, resp = self._make_rest_call(url_get_token, action_result, data=body, headers=headers, ignore_base_url=True, method="post")
        if phantom.is_fail(ret_val):
            return ret_val

        self._oauth_token = resp['access_token']
        self._base_url = resp['instance_url']
        return phantom.APP_SUCCESS

    def _retrieve_oauth_token_username_password(self, action_result):
        config = self.get_config()
        client_id = config['client_id']
        client_secret = config['client_secret']

        body = {
            'grant_type': 'password',
            'client_id': client_id,
            'client_secret': client_secret,
            'username': self._username,
            'password': self._password,

        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        if config.get('is_test_environment'):
            url_get_token = URL_GET_TOKEN_TEST
        else:
            url_get_token = URL_GET_TOKEN

        ret_val, resp = self._make_rest_call(url_get_token, action_result, data=body, headers=headers, ignore_base_url=True, method="post")
        if phantom.is_fail(ret_val):
            return ret_val

        self._oauth_token = resp['access_token']
        self._base_url = resp['instance_url']
        return phantom.APP_SUCCESS

    def _retrieve_oauth_token_helper(self, action_result):
        if self._auth_flow == self.OAUTH_FLOW:
            return self._retrieve_oauth_token(action_result)
        return self._retrieve_oauth_token_username_password(action_result)

    def _make_rest_call_helper(self, endpoint, action_result, headers=None, *args, **kwargs):
        # Add Authorization header before making rest call
        if headers is None:
            headers = {}

        if not self._oauth_token:
            self.save_progress("Retrieving API URL and OAuth Token...")
            ret_val = self._retrieve_oauth_token_helper(action_result)
            if phantom.is_fail(ret_val):
                return RetVal(ret_val)

        headers.update({
            'Authorization': 'Bearer {}'.format(self._oauth_token)
        })

        return self._make_rest_call(endpoint, action_result, headers=headers, *args, **kwargs)

    def _get_asset_name(self, action_result):

        asset_id = self.get_asset_id()

        rest_endpoint = PHANTOM_ASSET_INFO_URL.format(asset_id=asset_id)

        ret_val, resp_json = self._make_rest_call(rest_endpoint, action_result, ignore_base_url=True, verify=False)

        if (phantom.is_fail(ret_val)):
            return (ret_val, None)

        asset_name = resp_json.get('name')

        if (not asset_name):
            return (action_result.set_status(phantom.APP_ERROR, "Asset Name for id: {0} not found.".format(asset_id), None))

        return (phantom.APP_SUCCESS, asset_name)

    def _get_phantom_base_url(self, action_result):

        ret_val, resp_json = self._make_rest_call(PHANTOM_SYS_INFO_URL, action_result, ignore_base_url=True, verify=False)

        if (phantom.is_fail(ret_val)):
            return (ret_val, None)

        phantom_base_url = resp_json.get('base_url')

        if (not phantom_base_url):
            return (action_result.set_status(phantom.APP_ERROR,
                "Phantom Base URL not found in System Settings. Please specify this value in System Settings"), None)

        return (phantom.APP_SUCCESS, phantom_base_url)

    def _get_url_to_app_rest(self, action_result=None):

        if (not action_result):
            action_result = ActionResult()

        # get the phantom ip to redirect to
        ret_val, phantom_base_url = self._get_phantom_base_url(action_result)

        if (phantom.is_fail(ret_val)):
            return (action_result.get_status(), None)

        # get the asset name
        ret_val, asset_name = self._get_asset_name(action_result)

        if (phantom.is_fail(ret_val)):
            return (action_result.get_status(), None)

        self.save_progress('Using Phantom base URL as: {0}'.format(phantom_base_url))

        app_json = self.get_app_json()

        app_name = app_json['name']

        app_dir_name = _get_dir_name_from_app_name(app_name)

        url_to_app_rest = "{0}/rest/handler/{1}_{2}/{3}".format(phantom_base_url, app_dir_name, app_json['appid'], asset_name)

        return (phantom.APP_SUCCESS, url_to_app_rest)

    def _oauth_flow_test_connect(self, action_result):
        config = self.get_config()
        client_id = config['client_id']
        client_secret = config['client_secret']

        ret_val, app_rest_url = self._get_url_to_app_rest(action_result)
        if phantom.is_fail(ret_val):
            self.save_progress("Error getting redirect URL")
            return ret_val

        asset_id = self.get_asset_id()
        params = {
            'response_type': 'code',
            'state': asset_id,
            'redirect_uri': app_rest_url + '/start_oauth',
            'client_id': client_id,
            'client_secret': client_secret
        }

        if config.get('is_test_environment'):
            url_get_code = URL_GET_CODE_TEST
            url_get_token = URL_GET_TOKEN_TEST
        else:
            url_get_code = URL_GET_CODE
            url_get_token = URL_GET_TOKEN

        prep = requests.Request('post', url_get_code, params=params).prepare()

        creds = encryption_helper.encrypt(json.dumps(params), asset_id)  # pylint: disable=E1101
        url = encryption_helper.encrypt(prep.url, asset_id)  # pylint: disable=E1101

        state = {}
        state['creds'] = creds
        state['url'] = url
        state['url_get_token'] = url_get_token
        _save_app_state(state, asset_id)

        self.save_progress("To Continue, open this link in a new tab in your browser")
        self.save_progress(app_rest_url + '/redirect?asset_id={}'.format(asset_id))

        # Wait for user to authorize Salesforce
        for _ in range(0, 60):
            state = _load_app_state(asset_id)
            refresh_token = state.get('refresh_token')
            if refresh_token:
                break
            elif state.get('error', False):
                self.save_progress("Error retrieving refresh token")
                _delete_app_state(asset_id)
                return action_result.set_status(phantom.APP_ERROR)
            time.sleep(5)
        else:
            _delete_app_state(asset_id)
            self.save_progress("Unable to finish test connectivity due to time out")
            return action_result.set_status(phantom.APP_ERROR)

        _delete_app_state(asset_id)
        self._state = {}
        self._state['refresh_token'] = refresh_token

        self.save_progress("Successfully Retrieved Refresh Token")
        return phantom.APP_SUCCESS

    def _handle_test_connectivity(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        if self._auth_flow == self.OAUTH_FLOW:
            ret_val = self._oauth_flow_test_connect(action_result)
            if phantom.is_fail(ret_val):
                return ret_val

        self.save_progress("Obtaining API Version")

        ret_val, response = self._make_rest_call_helper('/services/data/', action_result)
        if phantom.is_fail(ret_val):
            return ret_val

        latest_version = response[-1]['url']
        self._state['latest_version'] = latest_version

        self.save_progress("Testing API Version and Authorization Credentials...")
        ret_val, response = self._make_rest_call_helper(latest_version, action_result)
        if phantom.is_fail(ret_val):
            return ret_val

        self.save_progress("Test Connectivity Passed")

        return action_result.set_status(phantom.APP_SUCCESS)

    def _get_run_query_results(self, action_result, endpoint, params):
        done = False
        while not done:
            ret_val, response = self._make_rest_call_helper(endpoint, action_result, params=params)
            if phantom.is_fail(ret_val):
                return ret_val
            done = response['done']
            if not done:
                params = None
                endpoint = response['nextRecordsUrl']

            for record in response['records']:
                action_result.add_data(record)

        action_result.update_summary({'num_objects': action_result.get_data_size()})
        return phantom.APP_SUCCESS

    def _handle_run_query(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        query = param['query']
        query_type = param.get('endpoint', 'query')

        endpoint = API_ENDPOINT_RUN_QUERY.format(
            version=self._version_uri,
            query_type=query_type
        )
        # Replace all spaces with a '+' sign for URL param
        query = ' '.join(query.split()).replace(' ', '+')
        # Pass a string to avoid getting the '+' url encoded
        params = 'q={}'.format(query)

        ret_val = self._get_run_query_results(action_result, endpoint, params)
        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully Retrieved Query Results")

    def _create_object(self, action_result, param, field_values):
        sobject = param.get('sobject', 'Case')

        endpoint = API_ENDPOINT_OBJECT.format(
            version=self._version_uri,
            sobject=sobject
        )

        ret_val, response = self._make_rest_call_helper(endpoint, action_result, json=field_values, method="post")
        if phantom.is_fail(ret_val):
            return ret_val

        action_result.add_data(response)
        summary = action_result.update_summary({})
        summary['obj_id'] = response['id']

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully created a new {}".format(sobject))

    def _handle_create_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        other = param['field_values']
        try:
            other_dict = json.loads(other)
        except Exception as e:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error reading 'field_values'",
                e
            )

        return self._create_object(action_result, param, other_dict)

    def _handle_create_ticket(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        other = param.get('field_values')
        if other:
            try:
                other_dict = json.loads(other)
            except Exception as e:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Error reading 'field_values'",
                    e
                )
        else:
            other_dict = {}

        for k, v in param.iteritems():
            if k in CASE_FIELD_MAP:
                other_dict[CASE_FIELD_MAP[k]] = v

        return self._create_object(action_result, param, other_dict)

    def _delete_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = param.get('sobject', 'Case')
        obj_id = param['id']

        endpoint = API_ENDPOINT_OBJECT_ID.format(
            version=self._version_uri,
            sobject=sobject,
            id=obj_id
        )

        ret_val, response = self._make_rest_call_helper(endpoint, action_result, method="delete")
        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully deleted {}".format(sobject))

    def _handle_delete_object(self, param):
        return self._delete_object(param)

    def _handle_delete_ticket(self, param):
        return self._delete_object(param)

    def _update_object(self, action_result, param, field_values):
        sobject = param.get('sobject', 'Case')
        obj_id = param['id']

        endpoint = API_ENDPOINT_OBJECT_ID.format(
            version=self._version_uri,
            sobject=sobject,
            id=obj_id
        )

        ret_val, response = self._make_rest_call_helper(endpoint, action_result, json=field_values, method="patch")
        if phantom.is_fail(ret_val):
            return ret_val

        action_result.add_data(response)
        summary = action_result.update_summary({})
        summary['obj_id'] = obj_id

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully updated {}".format(sobject))

    def _handle_update_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        other = param['field_values']
        try:
            other_dict = json.loads(other)
        except Exception as e:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error reading 'field_values'",
                e
            )

        return self._update_object(action_result, param, other_dict)

    def _handle_update_ticket(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        other = param.get('field_values')
        if other:
            try:
                other_dict = json.loads(other)
            except Exception as e:
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Error reading 'field_values'",
                    e
                )
        else:
            other_dict = {}

        for k, v in param.iteritems():
            if k in CASE_FIELD_MAP:
                other_dict[CASE_FIELD_MAP[k]] = v

        return self._update_object(action_result, param, other_dict)

    def _get_listview_results_url(self, action_result, endpoint, view_name):
        found_views = []
        done = False

        while not done:
            ret_val, response = self._make_rest_call_helper(endpoint, action_result)
            if phantom.is_fail(ret_val):
                return ret_val, None, None
            done = response['done']
            if not done:
                endpoint = response['nextRecordsUrl']

            for view in response['listviews']:
                if view_name and view['developerName'] == view_name:
                    return phantom.APP_SUCCESS, view['resultsUrl'], None
                found_views.append(view['developerName'])

        # Was not able to find view
        return phantom.APP_SUCCESS, None, found_views

    def _mogrify_record(self, record):
        # Transform a list of JSON objects into a dictionary
        columns = record['columns']
        columns_dict = {x.pop('fieldNameOrPath').replace('.', '_'): x for x in columns}
        record['columns'] = columns_dict
        return record

    def _get_listview_results_records(self, action_result, endpoint, params):
        done = False
        while not done:
            ret_val, response = self._make_rest_call_helper(endpoint, action_result, params=params)
            if phantom.is_fail(ret_val):
                return ret_val
            done = response['done']
            if not done:
                endpoint = response['nextRecordsUrl']

            for record in response['records']:
                action_result.add_data(self._mogrify_record(record))

        action_result.update_summary({'num_objects': action_result.get_data_size()})
        return phantom.APP_SUCCESS

    def _list_objects(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = param.get('sobject', 'Case')
        view_name = param.get('view_name')

        endpoint = API_ENDPOINT_GET_LISTVIEWS.format(
            version=self._version_uri,
            sobject=sobject
        )

        ret_val, results_url, views = self._get_listview_results_url(action_result, endpoint, view_name)
        if phantom.is_fail(ret_val):
            return ret_val
        elif not results_url and view_name:
            # They searched for an invalid view
            action_result.update_summary({'view_names': views})
            return action_result.set_status(phantom.APP_ERROR, "No listview with that specified name was found")
        elif not results_url and not view_name:
            # Just return a list of valid views
            action_result.update_summary({'view_names': views})
            return action_result.set_status(
                phantom.APP_SUCCESS,
                "Created a list of valid view names"
            )

        params = {
            'limit': param.get('limit', 25),
            'offset': param.get('offset', 0)
        }

        # Retrieve the list of objects
        endpoint = results_url
        ret_val = self._get_listview_results_records(action_result, endpoint, params)
        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully created a list of {} objects".format(sobject))

    def _handle_list_objects(self, param):
        return self._list_objects(param)

    def _handle_list_tickets(self, param):
        return self._list_objects(param)

    def _get_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = param.get('sobject', 'Case')
        obj_id = param['id']

        endpoint = API_ENDPOINT_OBJECT_ID.format(
            version=self._version_uri,
            sobject=sobject,
            id=obj_id
        )

        ret_val, response = self._make_rest_call_helper(endpoint, action_result)
        if phantom.is_fail(ret_val):
            return ret_val

        action_result.add_data(response)

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully retrieved {}".format(sobject))

    def _handle_get_object(self, param):
        return self._get_object(param)

    def _handle_get_ticket(self, param):
        return self._get_object(param)

    def _handle_post_chatter(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        parent_case_id = param['id']
        body = param['body']
        title = param.get('title')

        new_feed_item = {
            'ParentId': parent_case_id,
            'Title': title,
            'Body': body,
            'Type': 'TextPost'
        }

        ret_val = self._create_object(action_result, {'sobject': 'FeedItem'}, new_feed_item)
        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully posted to chatter")

    def _object_response_to_container(self, response, sobject):
        container = {}
        artifact = {}
        cef = {}
        cef_types = {}

        container['artifacts'] = [artifact]
        artifact['cef'] = cef
        artifact['cef_types'] = cef_types

        skip_field_names = {'attributes'}

        severity_mapping = {
            'severity 1 (high impact)': 'high',
            'severity 2 (medium impact': 'medium',
            'severity 3 (low impact)': 'low',
            'severity 4 (false positive)': 'low'
        }

        sensitivity_mapping = {
            'sensitive': 'red',
            'not sensitive': 'white'
        }

        container_name = None

        for k, v in response.iteritems():
            if k in skip_field_names:
                continue
            name = self._cef_name_map.get(k, k)
            cef[name] = v
            if k.endswith('Id') and v is not None:
                cef_types[name] = [ 'salesforce object id' ]

            if name == 'Subject':
                container_name = v

        if container_name is None:
            number = response.get('CaseNumber') or response.get('Id', '')
            container_name = "Salesforce {} Object # {}".format(sobject, number)

        container['name'] = container_name
        artifact['name'] = sobject

        container['source_data_identifier'] = hashlib.sha256('{}{}'.format(sobject, response['Id'])).hexdigest()

        severity = response.get('Incident_Severity__c')
        if severity:
            container['severity'] = severity_mapping.get(severity.lower(), 'medium')

        sensitivity = response.get('Incident_Sensitivity__c')
        if sensitivity:
            container['sensitivity'] = sensitivity_mapping.get(sensitivity.lower(), 'amber')

        return container

    def _batch_response_to_containers(self, response, sobject):
        containers = []

        self.debug_print('BATCH REQUEST HAS ERRORS: {}'.format(response['hasErrors']))

        results = response['results']
        for result in results:
            if result['statusCode'] != 200:
                self.debug_print('Got bad status code for response: {}'.format(result))
                continue

            # response here matches a single call to get object endpoint
            response = result['result']
            containers.append(self._object_response_to_container(response, sobject))

        return containers

    def _create_containers_from_records(self, action_result, records, sobject):
        num_records = len(records)
        cur_index = 0
        # Number of requests per batch (API only supports 25)
        num_batch = 25
        containers = []

        endpoint = API_ENDPOINT_BATCH_REQUEST.format(
            version=self._version_uri
        )

        # Since we need to individually retrieve each object, we can reduce the total number
        #  of API calls we need to make by using batch requests (up to 25x less!)
        while cur_index < num_records:
            batch_records = records[cur_index:cur_index + num_batch]
            batch_request = []
            for record in batch_records:
                record = self._mogrify_record(record)
                batch_request.append({
                    'method': 'GET',
                    'url': API_ENDPOINT_OBJECT_ID.format(
                        version=self._version_uri,
                        sobject=sobject,
                        id=record['columns']['Id']['value']
                    )
                })

            data = {
                'batchRequests': batch_request
            }

            ret_val, response = self._make_rest_call_helper(
                endpoint,
                action_result,
                json=data,
                method='post'
            )
            if phantom.is_fail(ret_val):
                return RetVal(
                    action_result.set_status(
                        phantom.APP_ERROR,
                        "Error retrieving objects: {}".format(action_result.get_message())
                    )
                )

            containers.extend(self._batch_response_to_containers(response, sobject))

            cur_index += num_batch

        return RetVal(phantom.APP_SUCCESS, containers)

    def _poll_for_all_objects(self, action_result, endpoint, offset):
        MAX_OBJECTS_PER_POLL = 500

        done = False

        records = []

        while not done:
            params = {
                'limit': MAX_OBJECTS_PER_POLL,
                'offset': offset
            }
            ret_val, response = self._make_rest_call_helper(endpoint, action_result, params=params)
            if phantom.is_fail(ret_val):
                return RetVal(None, None)

            num_returned = response['size']
            offset += num_returned
            if num_returned < MAX_OBJECTS_PER_POLL:
                done = True

            records.extend(response['records'])

        return RetVal(offset, records)

    def _handle_on_poll(self, param):
        config = self.get_config()
        action_result = self.add_action_result(ActionResult(dict(param)))

        sobject = config.get('poll_sobject', 'Case')
        view_name = config.get('poll_view_name')
        cef_name_map = config.get('cef_name_map')
        if cef_name_map:
            try:
                self._cef_name_map = json.loads(cef_name_map)
            except Exception as e:
                return action_result.set_status(phantom.APP_ERROR, "Error parsing cef_name_map", e)
        else:
            self._cef_name_map = {}

        max_containers = None

        if view_name is None:
            return action_result.set_status(phantom.APP_ERROR, "Error: Must specify poll_view_name")

        cur_offset = self._state.get('cur_offset')
        if cur_offset is None:
            # First time this app has done (none POLL NOW) ingestion
            cur_offset = 0
            max_containers = config.get('first_ingestion_max', 10)

        if self.is_poll_now():
            max_containers = param.get('container_count', 10)

        self.save_progress("Retrieving List View URI")
        endpoint = API_ENDPOINT_GET_LISTVIEWS.format(
            version=self._version_uri,
            sobject=sobject
        )

        ret_val, results_url, views = self._get_listview_results_url(action_result, endpoint, view_name)
        if phantom.is_fail(ret_val):
            return ret_val
        elif not results_url:
            return action_result.set_status(phantom.APP_ERROR, "No listview with that specified name was found")

        self.save_progress("Retrieved List View URI")
        self.save_progress("Getting new {} objects...".format(sobject))

        new_offset, records = self._poll_for_all_objects(action_result, results_url, cur_offset)
        if new_offset is None:
            return action_result.get_status()

        # Get most recent containers
        if max_containers:
            records = records[0 - int(max_containers):]

        ret_val, containers = self._create_containers_from_records(action_result, records, sobject)
        if phantom.is_fail(ret_val):
            return ret_val

        self.save_progress("Saving containers")

        for container in containers:
            ret_val, msg, container_id = self.save_container(container)
            if phantom.is_fail(ret_val):
                self.debug_print("Error saving container: {}".format(msg))

        if not self.is_poll_now():
            self._state['cur_offset'] = new_offset

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully ingested containers")

    def handle_action(self, param):

        ret_val = phantom.APP_SUCCESS

        # Get the action that we are supposed to execute for this App Run
        action_id = self.get_action_identifier()

        self.debug_print("action_id", self.get_action_identifier())

        if action_id == 'test_connectivity':
            ret_val = self._handle_test_connectivity(param)

        elif action_id == 'run_query':
            ret_val = self._handle_run_query(param)

        elif action_id == 'create_object':
            ret_val = self._handle_create_object(param)

        elif action_id == 'create_ticket':
            ret_val = self._handle_create_ticket(param)

        elif action_id == 'delete_object':
            ret_val = self._handle_delete_object(param)

        elif action_id == 'delete_ticket':
            ret_val = self._handle_delete_ticket(param)

        elif action_id == 'update_object':
            ret_val = self._handle_update_object(param)

        elif action_id == 'update_ticket':
            ret_val = self._handle_update_ticket(param)

        elif action_id == "get_object":
            ret_val = self._handle_get_object(param)

        elif action_id == 'get_ticket':
            ret_val = self._handle_get_ticket(param)

        elif action_id == 'list_objects':
            ret_val = self._handle_list_objects(param)

        elif action_id == 'list_tickets':
            ret_val = self._handle_list_tickets(param)

        elif action_id == "post_chatter":
            ret_val = self._handle_post_chatter(param)

        elif action_id == 'on_poll':
            ret_val = self._handle_on_poll(param)

        return ret_val

    def initialize(self):

        # Load the state in initialize, use it to store data
        # that needs to be accessed across actions
        self._state = self.load_state()
        config = self.get_config()
        self._username = config.get('username')
        self._password = config.get('password')
        if self._username:
            if not self._password:
                return self.set_status(
                    phantom.APP_ERROR,
                    "Password must be specified with a username"
                )
            self._auth_flow = self.USERNAME_PASSWORD

        if self.get_action_identifier() != "test_connectivity":
            try:
                self._version_uri = self._state['latest_version']
            except KeyError:
                return self.set_status(
                    phantom.APP_ERROR,
                    "Unable to retrieve API version. Has test connectivity been ran?"
                )
        return phantom.APP_SUCCESS

    def finalize(self):

        # Save the state, this data is saved accross actions and app upgrades
        self.save_state(self._state)
        return phantom.APP_SUCCESS


if __name__ == '__main__':

    import sys
    import pudb
    import argparse

    pudb.set_trace()

    argparser = argparse.ArgumentParser()

    argparser.add_argument('input_test_json', help='Input Test JSON file')
    argparser.add_argument('-u', '--username', help='username', required=False)
    argparser.add_argument('-p', '--password', help='password', required=False)

    args = argparser.parse_args()
    session_id = None

    username = args.username
    password = args.password

    if (username is not None and password is None):

        # User specified a username but not a password, so ask
        import getpass
        password = getpass.getpass("Password: ")

    if (username and password):
        try:
            print ("Accessing the Login page")
            r = requests.get("https://127.0.0.1/login", verify=False)
            csrftoken = r.cookies['csrftoken']

            data = dict()
            data['username'] = username
            data['password'] = password
            data['csrfmiddlewaretoken'] = csrftoken

            headers = dict()
            headers['Cookie'] = 'csrftoken=' + csrftoken
            headers['Referer'] = 'https://127.0.0.1/login'

            print ("Logging into Platform to get the session id")
            r2 = requests.post("https://127.0.0.1/login", verify=False, json=data, headers=headers)
            session_id = r2.cookies['sessionid']
        except Exception as e:
            print ("Unable to get session id from the platfrom. Error: " + str(e))
            exit(1)

    if (len(sys.argv) < 2):
        print "No test json specified as input"
        exit(0)

    with open(sys.argv[1]) as f:
        in_json = f.read()
        in_json = json.loads(in_json)
        print(json.dumps(in_json, indent=4))

        connector = SalesforceConnector()
        connector.print_progress_message = True

        if (session_id is not None):
            in_json['user_session_token'] = session_id

        ret_val = connector._handle_action(json.dumps(in_json), None)
        print (json.dumps(json.loads(ret_val), indent=4))

    exit(0)
