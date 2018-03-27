'''Integration tests for request-ride-event'''
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=redefined-outer-name
import json
import os

import boto3
from botocore.vendored import requests
import pytest
import warrant

EVENT_FILE = os.path.join(
    os.path.dirname(__file__),
    '..',
    '..',
    'events',
    'request-ride-event.json'
)

STACK_NAME = 'wild-rydes-ride-requests-tmc'
ENDPOINT_OUTPUT_NAME = 'ServiceEndpoint'
RIDE_REQUEST_PATH = '/ride'

AUTHORIZATION_STACK_NAME = 'wild-rydes-auth-tmc'
AUTHORIZATION_COGNITO_POOL_OUTPUT_NAME = 'UserPoolId'
AUTHORIZATION_COGNITO_CLIENT_OUTPUT_NAME = 'UserPoolClientId'


# FIXME: We chould automate creating and destroying this user through the AWS
# API possibly.
CICD_USER = 'tom+cicd-testing@serverlessops.io'
CICD_USER_PASSWORD = 'Testing123!'


def _get_output_value_from_cfn(stack_name, output_key):
    '''Get an aoutput from a stack'''
    cfn = boto3.client('cloudformation')
    stacks = cfn.describe_stacks()

    for s in stacks.get('Stacks'):
        if s.get('StackName') == stack_name:
            stack = s
            break
    assert stack is not None

    for output in stack.get('Outputs'):
        if output.get('OutputKey') == output_key:
            value = output.get('OutputValue')

    return value


@pytest.fixture
def request_data() -> str:
    '''Function trigger event'''
    with open(EVENT_FILE) as f:
        return json.load(f).get('body')


@pytest.fixture
def website_url() -> str:
    '''website URL'''
    site_url = _get_output_value_from_cfn(
        STACK_NAME,
        ENDPOINT_OUTPUT_NAME
    )
    assert site_url is not None
    return site_url + RIDE_REQUEST_PATH


@pytest.fixture
def authorization() -> str:
    '''Get authorization for testing.'''
    cognito_pool_id = _get_output_value_from_cfn(
        AUTHORIZATION_STACK_NAME,
        AUTHORIZATION_COGNITO_POOL_OUTPUT_NAME
    )

    cognito_client_id = _get_output_value_from_cfn(
        AUTHORIZATION_STACK_NAME,
        AUTHORIZATION_COGNITO_CLIENT_OUTPUT_NAME
    )

    ident = warrant.AWSSRP(
        CICD_USER,
        CICD_USER_PASSWORD,
        cognito_pool_id,
        cognito_client_id
    )

    auth = ident.authenticate_user()
    token = auth.get('AuthenticationResult').get('IdToken')

    return token


def test_request_ride_endpoint_no_auth(website_url, request_data):
    '''test API gateway + lambda integration'''
    resp = requests.post(website_url, json=request_data)

    # Check status code
    assert resp.status_code == 401


def test_request_ride_endpoint(website_url, request_data, authorization):
    '''test API gateway + lambda integration'''
    headers = {'Authorization': authorization}
    resp = requests.post(website_url, headers=headers, data=request_data)

    # Check status code
    assert resp.status_code == 201

    # Check we have appropriate response data
    j = resp.json()
    assert j.get('RideId') is not None
    assert j.get('Unicorn') is not None
    assert j.get('UnicornName') is not None
    assert j.get('Eta') is not None
    assert j.get('Rider') is not None
    assert j.get('RequestTime') is not None



