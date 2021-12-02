# File: salesforce_connector.py
#
# Copyright (c) 2017-2021 Splunk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under
# the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied. See the License for the specific language governing permissions
# and limitations under the License.
#
#
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
from bs4 import BeautifulSoup, UnicodeDammit
from django.http import HttpResponse
# from django.utils.dateparse import parse_datetime
# from datetime import datetime, timedelta
import hashlib
import sys


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


def _load_app_state(asset_id, app_connector=None):
    """ This function is used to load the current state file.

    :param asset_id: asset_id
    :param app_connector: Object of app_connector class
    :return: state: Current state file as a dictionary
    """

    asset_id = str(asset_id)
    if not asset_id or not asset_id.isalnum():
        if app_connector:
            app_connector.debug_print('In _load_app_state: Invalid asset_id')
        return {}

    app_dir = os.path.dirname(os.path.abspath(__file__))
    state_file = '{0}/{1}_state.json'.format(app_dir, asset_id)
    real_state_file_path = os.path.realpath(state_file)
    if not os.path.dirname(real_state_file_path) == app_dir:
        if app_connector:
            app_connector.debug_print('In _load_app_state: Invalid asset_id')
        return {}

    state = {}
    try:
        with open(real_state_file_path, 'r') as state_file_obj:
            state_file_data = state_file_obj.read()
            state = json.loads(state_file_data)
    except Exception as e:
        if app_connector:
            app_connector.debug_print('In _load_app_state: Exception: {0}'.format(str(e)))

    if app_connector:
        app_connector.debug_print('Loaded state: ', state)

    return state


def _save_app_state(state, asset_id, app_connector=None):
    """ This function is used to save current state in file.

    :param state: Dictionary which contains data to write in state file
    :param asset_id: asset_id
    :param app_connector: Object of app_connector class
    :return: status: phantom.APP_SUCCESS
    """

    asset_id = str(asset_id)
    if not asset_id or not asset_id.isalnum():
        if app_connector:
            app_connector.debug_print('In _save_app_state: Invalid asset_id')
        return {}

    app_dir = os.path.split(__file__)[0]
    state_file = '{0}/{1}_state.json'.format(app_dir, asset_id)

    real_state_file_path = os.path.realpath(state_file)
    if not os.path.dirname(real_state_file_path) == app_dir:
        if app_connector:
            app_connector.debug_print('In _save_app_state: Invalid asset_id')
        return {}

    if app_connector:
        app_connector.debug_print('Saving state: ', state)

    try:
        with open(real_state_file_path, 'w+') as state_file_obj:
            state_file_obj.write(json.dumps(state))
    except Exception as e:
        print('Unable to save state file: {0}'.format(str(e)))

    return phantom.APP_SUCCESS


def _return_error(msg, state, asset_id, status):
    state['error'] = True
    _save_app_state(state, asset_id)
    return HttpResponse(msg, status=status, content_type="text/plain")


def _handle_oauth_start(request, path_parts):
    # This is where we should land AFTER the redirect callback when the user authenticates on Salesforce
    # After that, it will retrieve the "code" which is sent, and then use that to retrieve the refresh_token
    asset_id = request.GET.get('state')
    if (not asset_id):
        return HttpResponse("ERROR: Asset ID not found in URL", content_type="text/plain", status=400)

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
                    url_get_token
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
        return HttpResponse("You can now close this page", content_type="text/plain")
    return _return_error(
        "Something went wrong during authentication",
        state, asset_id, 401
    )


def _handle_redirect(request, path_parts):
    asset_id = request.GET.get('asset_id')
    if (not asset_id):
        return HttpResponse("ERROR: Asset ID not found in URL", content_type="text/plain", status=400)

    state = _load_app_state(asset_id)
    if not state:
        return HttpResponse('ERROR: Invalid asset_id', content_type="text/plain", status=400)

    enc_url = state['url']
    dec_url = encryption_helper.decrypt(enc_url, asset_id)  # pylint: disable=E1101

    resp = HttpResponse(status=302)
    resp['location'] = dec_url
    return resp


def handle_request(request, path_parts):
    if len(path_parts) < 2:
        return HttpResponse("Invalid REST endpoint request", content_type="text/plain", status=404)

    call_type = path_parts[1]

    if call_type == 'redirect':
        return _handle_redirect(request, path_parts)

    if call_type == 'start_oauth':
        return _handle_oauth_start(request, path_parts)

    return HttpResponse("Invalid endpoint", content_type="text/plain", status=404)


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
        self._last_viewed_date = None

    def _handle_py_ver_compat_for_input_str(self, input_str):
        """
        This method returns the encoded|original string based on the Python version.
        :param input_str: Input string to be processed
        :return: input_str (Processed input string based on following logic 'input_str - Python 3; encoded input_str - Python 2')
        """
        try:
            if input_str and self._python_version < 3:
                input_str = UnicodeDammit(input_str).unicode_markup.encode('utf-8')
        except:
            self.debug_print("Error occurred while handling python 2to3 compatibility for the input string")

        return input_str

    def _get_error_message_from_exception(self, e):
        """ This function is used to get appropriate error message from the exception.
        :param e: Exception object
        :return: error message
        """
        error_msg = SALESFORCE_UNKNOWN_ERR_MSG
        error_code = SALESFORCE_ERR_CODE_UNAVAILABLE
        try:
            if e.args:
                if len(e.args) > 1:
                    error_code = e.args[0]
                    error_msg = e.args[1]
                elif len(e.args) == 1:
                    error_code = SALESFORCE_ERR_CODE_UNAVAILABLE
                    error_msg = e.args[0]
            else:
                error_code = SALESFORCE_ERR_CODE_UNAVAILABLE
                error_msg = SALESFORCE_UNKNOWN_ERR_MSG
        except:
            error_code = SALESFORCE_ERR_CODE_UNAVAILABLE
            error_msg = SALESFORCE_UNKNOWN_ERR_MSG

        try:
            error_msg = self._handle_py_ver_compat_for_input_str(error_msg)
        except TypeError:
            error_msg = SALESFORCE_UNICODE_DAMMIT_TYPE_ERR_MSG
        except:
            error_msg = SALESFORCE_UNKNOWN_ERR_MSG

        return "Error Code: {0}. Error Message: {1}".format(error_code, error_msg)

    def _validate_integers(self, action_result, parameter, key, allow_zero=False):
        """Validate the provided input parameter value is a non-zero positive integer and returns the integer value of the parameter itself.

        Parameters:
            :param action_result: object of ActionResult class
            :param parameter: input parameter
            :param key: string value of parameter name
            :param allow_zero: indicator for given parameter that whether zero value is allowed or not
        Returns:
            :return: integer value of the parameter
        """
        if parameter is not None:
            try:
                if not float(parameter).is_integer():
                    return action_result.set_status(phantom.APP_ERROR, "Please provide a valid integer value in the '{}' parameter".format(key)), None

                parameter = int(parameter)
            except:
                return action_result.set_status(phantom.APP_ERROR, "Please provide a valid integer value in the '{}' parameter".format(key)), None

            if parameter < 0:
                return action_result.set_status(phantom.APP_ERROR, "Please provide a valid non-negative integer value in the '{}' parameter".format(key)), None
            if not allow_zero and parameter == 0:
                return action_result.set_status(phantom.APP_ERROR, SALESFORCE_INVALID_INTEGER.format(parameter=key)), None

        return phantom.APP_SUCCESS, parameter

    def _process_empty_response(self, response, action_result):
        """Process empty response.

        Parameters:
            :param response: response data
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response
        """

        if self.get_action_identifier() in ('update_ticket', 'update_object', 'delete_object', 'delete_ticket'):
            return RetVal(phantom.APP_SUCCESS, {})

        if response.status_code == 200:
            return RetVal(phantom.APP_SUCCESS, {})

        return RetVal(action_result.set_status(phantom.APP_ERROR, "Empty response and no information in the header"), None)

    def _process_html_response(self, response, action_result):
        """Process html response.

        Parameters:
            :param response: response data
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response
        """
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

        message = "Status Code: {0}. Data from server:\n{1}\n".format(status_code, error_text)

        message = self._handle_py_ver_compat_for_input_str(message.replace('{', '{{').replace('}', '}}'))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_json_response(self, r, action_result):
        """Process json response.

        Parameters:
            :param r: response data
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response
        """

        # Try a json parse
        try:
            resp_json = r.json()
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Unable to parse JSON response. Error: {0}".format(error_message)), None)

        # Please specify the status codes here
        if 200 <= r.status_code < 399:
            return RetVal(phantom.APP_SUCCESS, resp_json)

        # You should process the error returned in the json
        error_message = self._handle_py_ver_compat_for_input_str(r.text.replace('{', '{{').replace('}', '}}'))
        message = "Error from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, error_message)

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _process_response(self, r, action_result):
        """Process API response.

        Parameters:
            :param r: response data
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response
        """

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

        # Process an HTML response, Do this no matter what the API talks.
        # There is a high chance of a PROXY in between phantom and the rest of
        # world, in case of errors, PROXY's return HTML, this function parses
        # the error and adds it to the action_result.
        if 'html' in r.headers.get('Content-Type', ''):
            return self._process_html_response(r, action_result)

        # it's not content-type that is to be parsed, handle an empty response
        if not r.text:
            return self._process_empty_response(r, action_result)

        # everything else is actually an error at this point
        message = "Can't process response from server. Status Code: {0} Data from server: {1}".format(
                r.status_code, self._handle_py_ver_compat_for_input_str(r.text.replace('{', '{{').replace('}', '}}')))

        return RetVal(action_result.set_status(phantom.APP_ERROR, message), None)

    def _make_rest_call(self, endpoint, action_result, headers=None, params=None, data=None, json=None, method="get", ignore_base_url=False, **kwargs):
        """Make the REST call to the app.

        Parameters:
            :param endpoint: REST endpoint
            :param action_result: object of ActionResult class
            :param headers: request headers
            :param params: request parameters
            :param data: request body
            :param json: JSON object
            :param method: GET/POST/PUT/DELETE/PATCH (Default will be GET)
            :param ignore_base_url: Ignore the base url and use endpoint as url (Default False)
            :param **kwargs: Dictionary of other parameters
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response obtained by making an API call
        """
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
                return RetVal(action_result.set_status(phantom.APP_ERROR, "Base URL Is None"), resp_json)
            url = "{0}{1}".format(self._base_url, endpoint)

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
            error_message = self._get_error_message_from_exception(e)
            return RetVal(action_result.set_status(phantom.APP_ERROR, "Error Connecting to server. Details: {0}".format(error_message)), resp_json)

        return self._process_response(r, action_result)

    def _retrieve_oauth_token(self, action_result):
        """ This function is used to get a Oauth token via REST Call.

        Parameters:
            :param action_result: Object of action result
        Returns:
            :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """

        config = self.get_config()
        client_id = self._handle_py_ver_compat_for_input_str(config['client_id'])
        client_secret = config['client_secret']
        try:
            refresh_token = encryption_helper.decrypt(self._state['refresh_token'], self.get_asset_id())  # pylint: disable=E1101
        except KeyError:
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error getting refresh token, has test connectivity been run?"
            )
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error decrypting refresh token", error_message
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
        """ This function is used to get a Oauth token via REST Call with username and password.

        Parameters:
            :param action_result: Object of action result
        Returns:
            :return: status(phantom.APP_SUCCESS/phantom.APP_ERROR)
        """

        config = self.get_config()
        client_id = self._handle_py_ver_compat_for_input_str(config['client_id'])
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
        """ Function that helps to retrieve oauth token for the app.

        Parameters:
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message)
        """
        if self._auth_flow == self.OAUTH_FLOW:
            return self._retrieve_oauth_token(action_result)
        return self._retrieve_oauth_token_username_password(action_result)

    def _make_rest_call_helper(self, endpoint, action_result, headers=None, *args, **kwargs):
        """ Function that helps setting REST call to the app.

        Parameters:
            :param endpoint: REST endpoint
            :param action_result: object of ActionResult class
            :param headers: request headers
            :param *args: parameters
            :param **kwargs: Dictionary of parameters
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), response obtained by making an API call
        """
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
        """ Get name of the asset using Phantom URL.

        Parameters:
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), asset name
        """

        asset_id = self.get_asset_id()

        rest_endpoint = PHANTOM_ASSET_INFO_URL.format(url=self.get_phantom_base_url(), asset_id=asset_id)

        ret_val, resp_json = self._make_rest_call(rest_endpoint, action_result, ignore_base_url=True, verify=False)

        if (phantom.is_fail(ret_val)):
            return (ret_val, None)

        asset_name = resp_json.get('name')

        if (not asset_name):
            return (action_result.set_status(phantom.APP_ERROR, "Asset Name for id: {0} not found.".format(asset_id), None))

        return (phantom.APP_SUCCESS, asset_name)

    def _get_phantom_base_url(self, action_result):
        """ Get base url of phantom.

        Parameters:
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message), base url of phantom
        """

        ret_val, resp_json = self._make_rest_call(PHANTOM_SYS_INFO_URL.format(url=self.get_phantom_base_url()), action_result, ignore_base_url=True, verify=False)

        if (phantom.is_fail(ret_val)):
            return (ret_val, None)

        phantom_base_url = resp_json.get('base_url').rstrip("/")

        if (not phantom_base_url):
            return (action_result.set_status(phantom.APP_ERROR,
                                             "Phantom Base URL not found in System Settings. Please specify this value in System Settings"), None)

        return (phantom.APP_SUCCESS, phantom_base_url)

    def _get_url_to_app_rest(self, action_result=None):
        """ Get URL for making rest calls.

        Parameters:
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS(along with appropriate message),
        URL to make rest calls
        """

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
        """ Function that handles the test connectivity action with Oauth(Authentication method).

        Parameters:
            :param action_result: object of ActionResult class
        Returns:
            :return: status phantom.APP_ERROR/phantom.APP_SUCCESS
        """

        config = self.get_config()
        client_id = self._handle_py_ver_compat_for_input_str(config['client_id'])
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
        _save_app_state(state, asset_id, self)

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
        """ Function that handles the test connectivity action """

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
        query = self._handle_py_ver_compat_for_input_str(param['query'])
        query_type = self._handle_py_ver_compat_for_input_str(param.get('endpoint', 'query'))

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
        sobject = self._handle_py_ver_compat_for_input_str(param.get('sobject', 'Case'))

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
        other = self._handle_py_ver_compat_for_input_str(param['field_values'])
        try:
            other_dict = json.loads(other)
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error reading 'field_values'",
                error_message
            )

        return self._create_object(action_result, param, other_dict)

    def _handle_create_ticket(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        other = self._handle_py_ver_compat_for_input_str(param.get('field_values'))
        if other:
            try:
                other_dict = json.loads(other)
            except Exception as e:
                error_message = self._get_error_message_from_exception(e)
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Error reading 'field_values'",
                    error_message
                )
        else:
            other_dict = {}

        for k, v in list(param.items()):
            if k in CASE_FIELD_MAP:
                other_dict[CASE_FIELD_MAP[k]] = v

        return self._create_object(action_result, param, other_dict)

    def _delete_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = self._handle_py_ver_compat_for_input_str(param.get('sobject', 'Case'))
        obj_id = self._handle_py_ver_compat_for_input_str(param['id'])

        endpoint = API_ENDPOINT_OBJECT_ID.format(
            version=self._version_uri,
            sobject=sobject,
            id=obj_id
        )

        ret_val, response = self._make_rest_call_helper(endpoint, action_result, method="delete")
        if phantom.is_fail(ret_val):
            return ret_val

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully deleted the {}".format(sobject))

    def _handle_delete_object(self, param):
        return self._delete_object(param)

    def _handle_delete_ticket(self, param):
        return self._delete_object(param)

    def _update_object(self, action_result, param, field_values):
        sobject = self._handle_py_ver_compat_for_input_str(param.get('sobject', 'Case'))
        obj_id = self._handle_py_ver_compat_for_input_str(param['id'])

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

        return action_result.set_status(phantom.APP_SUCCESS, "Successfully updated the {}".format(sobject))

    def _handle_update_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        other = self._handle_py_ver_compat_for_input_str(param.get('field_values'))
        try:
            other_dict = json.loads(other)
        except Exception as e:
            error_message = self._get_error_message_from_exception(e)
            return action_result.set_status(
                phantom.APP_ERROR,
                "Error reading 'field_values'",
                error_message
            )

        return self._update_object(action_result, param, other_dict)

    def _handle_update_ticket(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))

        other = self._handle_py_ver_compat_for_input_str(param.get('field_values'))
        if other:
            try:
                other_dict = json.loads(other)
            except Exception as e:
                error_message = self._get_error_message_from_exception(e)
                return action_result.set_status(
                    phantom.APP_ERROR,
                    "Error reading 'field_values'",
                    error_message
                )
        else:
            other_dict = {}

        for k, v in list(param.items()):
            if k in CASE_FIELD_MAP:
                other_dict[CASE_FIELD_MAP[k]] = v

        if not other_dict:
            return action_result.set_status(phantom.APP_ERROR, "Please provide at least one optional parameter for updating the Case")

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

    def _get_listview_results_records(self, action_result, endpoint, offset, limit):
        max_page_size = 2000
        records = []
        while True:
            params = {
                "limit": max_page_size,
                "offset": offset
            }

            ret_val, response = self._make_rest_call_helper(endpoint, action_result, params=params)

            if phantom.is_fail(ret_val):
                if "Maximum SOQL offset allowed is" in action_result.get_message():
                    self.save_progress("Because of the limitation of the offset value in the API, returning the maximum possible records")
                    self.debug_print("Because of the limitation of the offset value in the API, returning the maximum possible records")
                    self.debug_print("Response from the API: {}".format(action_result.get_message()))
                    break
                return ret_val

            records.extend(response.get('records', []))

            if len(records) >= limit:
                records = records[:limit]
                break

            if len(response.get('records', [])) < max_page_size:
                break

            offset += max_page_size

        for record in records:
            action_result.add_data(self._mogrify_record(record))

        action_result.update_summary({'num_objects': action_result.get_data_size()})
        return phantom.APP_SUCCESS

    def _list_objects(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = self._handle_py_ver_compat_for_input_str(param.get('sobject', 'Case'))
        view_name = self._handle_py_ver_compat_for_input_str(param.get('view_name'))

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
            return action_result.set_status(phantom.APP_ERROR, "Specified list view name was not found")
        elif not results_url and not view_name:
            # Just return a list of valid views
            action_result.update_summary({'view_names': views})
            return action_result.set_status(
                phantom.APP_SUCCESS,
                "Listed the valid view names"
            )

        # validate limit parameter
        ret_val, limit = self._validate_integers(action_result, param.get('limit', 25), "limit")
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # validate offset parameter
        ret_val, offset = self._validate_integers(action_result, param.get('offset', 0), "offset", allow_zero=True)
        if phantom.is_fail(ret_val):
            return action_result.get_status()

        # Retrieve the list of objects
        endpoint = results_url
        ret_val = self._get_listview_results_records(action_result, endpoint, offset, limit)
        if phantom.is_fail(ret_val):
            return ret_val

        if "Maximum SOQL offset allowed is" in action_result.get_message():
            message = "Because of the limitation of the offset value in the API, returning the maximum possible records."
            message += "Response from the API: {}".format(action_result.get_message())
        else:
            message = "Successfully fetched a list of {} objects".format(sobject)

        return action_result.set_status(phantom.APP_SUCCESS, message)

    def _handle_list_objects(self, param):
        return self._list_objects(param)

    def _handle_list_tickets(self, param):
        return self._list_objects(param)

    def _get_object(self, param):
        action_result = self.add_action_result(ActionResult(dict(param)))
        sobject = self._handle_py_ver_compat_for_input_str(param.get('sobject', 'Case'))
        obj_id = self._handle_py_ver_compat_for_input_str(param['id'])

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

        parent_case_id = self._handle_py_ver_compat_for_input_str(param['id'])
        body = self._handle_py_ver_compat_for_input_str(param['body'])
        title = self._handle_py_ver_compat_for_input_str(param.get('title'))

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

        for k, v in list(response.items()):
            if k in skip_field_names:
                continue
            name = self._cef_name_map.get(k, k)
            cef[name] = v
            if k.endswith('Id') and v is not None:
                cef_types[name] = ['salesforce object id']

            if name == 'Subject':
                container_name = v

        if container_name is None:
            number = response.get('CaseNumber') or response.get('Id', '')
            container_name = "Salesforce {} Object # {}".format(sobject, number)

        container['name'] = container_name
        artifact['name'] = sobject

        try:
            if not self._last_viewed_date:
                artifact["cef"].pop("LastViewedDate")
                artifact["cef"].pop("LastReferencedDate")
                self.save_progress("Removed LastViewedDate and LastReferencedDate from the artifact.")
        except:
            self.debug_print("LastViewedDate or LastReferencedDate may not be present in the artifact. Unable to remove LastViewedDate from the artifact")
            pass

        try:
            artifact['source_data_identifier'] = hashlib.sha256(json.dumps(artifact)).hexdigest()
            container['source_data_identifier'] = hashlib.sha256('{}{}'.format(sobject, response['Id'])).hexdigest()
        except:
            artifact['source_data_identifier'] = hashlib.sha256(json.dumps(artifact).encode()).hexdigest()
            container['source_data_identifier'] = hashlib.sha256('{}{}'.format(sobject, response['Id']).encode()).hexdigest()

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

    def _poll_for_all_objects(self, action_result, endpoint, offset, max_containers):
        MAX_OBJECTS_PER_POLL = 2000

        records = []
        while True:
            params = {
                'limit': MAX_OBJECTS_PER_POLL,
                'offset': offset
            }
            ret_val, response = self._make_rest_call_helper(endpoint, action_result, params=params)
            if phantom.is_fail(ret_val):
                if "Maximum SOQL offset allowed is" in action_result.get_message():
                    self.save_progress("Because of the limitation of the offset value in the API, returning the maximum possible records")
                    self.debug_print("Because of the limitation of the offset value in the API, returning the maximum possible records")
                    self.debug_print("Response from the API: {}".format(action_result.get_message()))
                    return RetVal(offset, records)
                return RetVal(None, None)

            records.extend(response.get('records', []))

            if max_containers and len(records) >= max_containers:
                offset += len(records[:max_containers])
                records = records[:max_containers]
                break

            if len(response.get('records', [])) < MAX_OBJECTS_PER_POLL:
                offset += len(response.get('records', []))
                break

            offset += MAX_OBJECTS_PER_POLL

        return RetVal(offset, records)

    def _handle_on_poll(self, param):
        config = self.get_config()
        action_result = self.add_action_result(ActionResult(dict(param)))

        sobject = self._handle_py_ver_compat_for_input_str(config.get('poll_sobject', 'Case'))
        view_name = self._handle_py_ver_compat_for_input_str(config.get('poll_view_name'))
        cef_name_map = self._handle_py_ver_compat_for_input_str(config.get('cef_name_map'))
        self._last_viewed_date = config.get("last_view_date", False)
        if cef_name_map:
            try:
                self._cef_name_map = json.loads(cef_name_map)
            except Exception as e:
                error_message = self._get_error_message_from_exception(e)
                return action_result.set_status(phantom.APP_ERROR, "Error parsing cef_name_map {}".format(error_message))
        else:
            self._cef_name_map = {}

        max_containers = None

        if view_name is None:
            return action_result.set_status(phantom.APP_ERROR, "Error: Must specify poll_view_name")

        if self.is_poll_now():
            cur_offset = 0
            # validate container_count parameter
            ret_val, max_containers = self._validate_integers(action_result, param.get('container_count', 10), "container_count")
            if phantom.is_fail(ret_val):
                return action_result.get_status()
        else:
            # validate cur_offset parameter
            ret_val, cur_offset = self._validate_integers(action_result, self._state.get('cur_offset', 0), "cur_offset", allow_zero=True)
            if phantom.is_fail(ret_val):
                return action_result.get_status()

            # validate first_ingestion_max parameter
            if not cur_offset:
                ret_val, max_containers = self._validate_integers(action_result, config.get('first_ingestion_max', 10), "first_ingestion_max")
                if phantom.is_fail(ret_val):
                    return action_result.get_status()

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

        new_offset, records = self._poll_for_all_objects(action_result, results_url, cur_offset, max_containers)
        if new_offset is None:
            return action_result.get_status()

        ret_val, containers = self._create_containers_from_records(action_result, records, sobject)
        if phantom.is_fail(ret_val):
            return ret_val

        self.save_progress("Saving containers")

        for container in containers:
            container_artifact = container.pop("artifacts")
            ret_val, msg, container_id = self.save_container(container)
            if phantom.is_fail(ret_val):
                self.save_progress("Error saving container: {}".format(msg))

            for artifact in container_artifact:
                artifact['container_id'] = container_id
            ret_val, status_string, artifact_ids = self.save_artifacts(container_artifact)
            if phantom.is_fail(ret_val):
                self.save_progress("Error saving artifacts: {}".format(status_string))

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

        # Fetching the Python major version
        try:
            self._python_version = int(sys.version_info[0])
        except:
            return self.set_status(phantom.APP_ERROR, "Error occurred while getting the Phantom server's Python major version.")

        self._username = self._handle_py_ver_compat_for_input_str(config.get('username'))
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

        # Save the state, this data is saved across actions and app upgrades
        self.save_state(self._state)
        return phantom.APP_SUCCESS


if __name__ == '__main__':

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
        login_url = BaseConnector._get_phantom_base_url() + 'login'
        try:
            print("Accessing the Login page")
            r = requests.get(login_url, verify=False)
            csrftoken = r.cookies['csrftoken']

            data = dict()
            data['username'] = username
            data['password'] = password
            data['csrfmiddlewaretoken'] = csrftoken

            headers = dict()
            headers['Cookie'] = 'csrftoken=' + csrftoken
            headers['Referer'] = login_url

            print("Logging into Platform to get the session id")
            r2 = requests.post(login_url, verify=False, json=data, headers=headers)
            session_id = r2.cookies['sessionid']
        except Exception as e:
            print("Unable to get session id from the platform. Error: " + str(e))
            exit(1)

    if (len(sys.argv) < 2):
        print("No test json specified as input")
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
        print(json.dumps(json.loads(ret_val), indent=4))

    exit(0)
