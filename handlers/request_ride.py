'''Request a ride'''

import datetime
import logging
import json
import os
import random
import string

import boto3
from botocore.vendored import requests

if os.environ.get('XRAY_ENABLED', '').lower() == 'true':
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core import patch_all

from iopipe.iopipe import IOpipe
from iopipe.contrib.profiler import ProfilerPlugin
from iopipe.contrib.trace import TracePlugin

# AWS X-Ray
if os.environ.get('XRAY_ENABLED', '').lower() == 'true':
    patch_all()

# logging
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logging.root.setLevel(logging.getLevelName(log_level))  # type:ignore
_logger = logging.getLogger(__name__)

# IOpipe
iopipe_plugins = []

iopipe_profiler_enabled = os.environ.get('IOPIPE_PROFILER_ENABLED', '').lower() == 'true'
if iopipe_profiler_enabled:
    iopipe_profiler_plugin = ProfilerPlugin(enabled=True)
    iopipe_plugins.append(iopipe_profiler_plugin)

iopipe_tracing_enabled = os.environ.get('IOPIPE_TRACING_ENABLED', '').lower() == 'true'
if iopipe_tracing_enabled:
    iopipe_tracing_plugin = TracePlugin(auto_measure=True)
    iopipe_plugins.append(iopipe_tracing_plugin)

iopipe_token = os.environ.get('IOPIPE_TOKEN') or None
iopipe = IOpipe(iopipe_token, plugins=iopipe_plugins)

# DynamoDB
DYNAMODB_TABLE = os.environ.get('DYNAMODB_TABLE')
dynamodb = boto3.resource('dynamodb')
ddt = dynamodb.Table(DYNAMODB_TABLE)

FLEET = [
    {
        'Name': 'Bucephalus',
        'Color': 'Golden',
        'Gender': 'Male',
    },
    {
        'Name': 'Shadowfax',
        'Color': 'White',
        'Gender': 'Male',
    },
    {
        'Name': 'Rocinante',
        'Color': 'Yellow',
        'Gender': 'Female',
    },

]

# Testing promo feature
PROMO_DISCOUNT_ENDPOINT = os.environ.get('PROMO_DISCOUNT_ENDPOINT')


def _get_ride_discount(user, pickup_location, url=PROMO_DISCOUNT_ENDPOINT):
    '''Check promo service for a discount multiplier'''
    resp = requests.post(url, json={'User': user, 'PickupLocation': pickup_location})
    return resp.json().get('DiscountMultiplier')


def _get_ride(user, pickup_location):
    '''Get a ride.'''
    ride_id = ''.join(random.choice(string.digits + string.ascii_letters) for _ in range(16))
    unicorn = _get_unicorn()
    eta = _get_unicorn_eta(unicorn, pickup_location)

    # NOTE: upstream they replace Rider with User but that seems silly.
    resp = {
        'RideId': ride_id,
        'Unicorn': unicorn,
        'UnicornName': unicorn.get('Name'),
        'Eta': '{} Seconds'.format(eta),
        'Rider': user,
        'RequestTime': str(datetime.datetime.now()),
    }
    return resp


def _get_unicorn():
    '''Return a unicorn from the fleet'''
    return FLEET[random.randint(0, len(FLEET) - 1)]


def _get_unicorn_eta(unicorn, pickup_location):
    '''Get arrival eta of unicorn.  Returns eta seconds as int.'''

    # This was found to be reasonably accurate and far cheaper than other
    # solutions tried.
    return 30


def _get_pickup_location(body):
    '''Return pickup location from event'''
    return body.get('PickupLocation')


def _get_authorizer_from_event(event):
    '''Get authorizer from event.'''
    return event.get('requestContext').get('authorizer')


def _get_user_from_authorizer(authorizer):
    '''Get username from authentication provider'''
    return authorizer.get('claims').get('cognito:username')


def _record_ride(ride_item):
    '''Record a ride.'''
    resp = ddt.put_item(
        TableName=DYNAMODB_TABLE,
        Item=ride_item
    )
    _logger.debug('_record_ride({}) -> {}'.format(ride_item, resp))


@iopipe
def handler(event, context):
    '''Function entry'''
    _logger.debug('Request: {}'.format(json.dumps(event)))

    # IOpipe state.
    if iopipe_tracing_enabled:
        _logger.info('iopipe_tracing_enabled: {}'.format(str(iopipe_tracing_enabled)))
    if iopipe_profiler_enabled:
        _logger.info('iopipe_profiler_enabled: {}'.format(str(iopipe_profiler_enabled)))

    authorizer = _get_authorizer_from_event(event)
    if authorizer is None:
        _logger.error('Authorization not configured')
        error_msg = {'error': 'There seems to be an error on our end.'}

        resp = {
            'statusCode': 500,
            'body': json.dumps(error_msg)
        }

    else:
        user = _get_user_from_authorizer(authorizer)
        body = json.loads(event.get('body'))
        pickup_location = _get_pickup_location(body)
        ride_resp = _get_ride(user, pickup_location)

        # Note: testing discount feature:
        discount_multiplier = _get_ride_discount(user, pickup_location)
        ride_resp['DiscountMultiplier'] = discount_multiplier

        _record_ride(ride_resp)

        resp = {
            'statusCode': 201,
            'body': json.dumps(ride_resp),
            'headers': {
                "Access-Control-Allow-Origin": "*",
            }
        }

    return resp

