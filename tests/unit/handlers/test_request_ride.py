'''Test request_ride'''
# pylint: disable=protected-access
# pylint: disable=wrong-import-position
# pylint: disable=redefined-outer-name
import datetime
import json
import os
import pytest

# Need to ensure function environment settings are set before import
os.environ['DYNAMODB_TABLE'] = 'test-db'
import handlers.request_ride as h


EVENT_FILE = os.path.join(
    os.path.dirname(__file__),
    '..',
    '..',
    'events',
    'request-ride-event.json'
)


@pytest.fixture
def event() -> dict:
    '''Function trigger event'''
    with open(EVENT_FILE) as f:
        return json.load(f)


@pytest.fixture
def authorizer(event) -> dict:
    '''Event authorizer'''
    return event.get('requestContext').get('authorizer')


@pytest.fixture
def body(event) -> dict:
    '''Event request body'''
    return json.loads(event.get('body'))


@pytest.fixture
def pickup_location(body) -> dict:
    '''Pickup location'''
    return body.get('PickupLocation')


@pytest.fixture
def ride_id() -> str:
    '''Ride Id'''
    return 'testRideId'


@pytest.fixture
def ride(ride_id, user, unicorn, dt=str(datetime.datetime.now())) -> dict:
    '''Unicorn ride item'''
    ride = {
        'RideId': ride_id,
        'Rider': user,
        'Unicorn': unicorn,
        'UnicornName': unicorn.get('Name'),
        'Eta': 30,
        'RequestTime': dt
    }

    return ride


@pytest.fixture
def unicorn() -> dict:
    '''Random unicorn'''
    unicorn = {
        'Name': 'TestUnicorn',
        'Color': 'Golden',
        'Gender': 'Male',
    }
    return unicorn


@pytest.fixture
def user(authorizer) -> str:
    '''Event authorizer user'''
    return authorizer.get('claims').get('cognito:username')


def test__get_authorizer_from_event(event, authorizer):
    '''test _get_authorizer_from_event'''
    this_authorizer = h._get_authorizer_from_event(event)
    assert this_authorizer == authorizer


def test__get_pickup_location(body, pickup_location):
    '''Return pickup location from event'''
    this_pl = h._get_pickup_location(body)
    assert this_pl == pickup_location


def test__get_user_from_authorizer(authorizer, user):
    '''Get username from authentication provider'''
    this_user = h._get_user_from_authorizer(authorizer)
    assert this_user == user


def test__get_ride(user, pickup_location, ride):
    '''test _get_ride'''
    this_ride = h._get_ride(user, pickup_location)
    # Just checking the shape of the response
    assert 'RideId' in this_ride.keys()
    assert 'Unicorn' in this_ride.keys()
    assert 'UnicornName' in this_ride.keys()
    assert 'Rider' in this_ride.keys()
    assert 'Eta' in this_ride.keys()
    assert 'RequestTime' in this_ride.keys()

