import pytest
import requests_mock
import app as webapp_module
from app import app
from datetime import datetime, timedelta

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_index_success(client):
    with requests_mock.Mocker() as m:
        m.get('http://checkin-service:5000/api/rooms', json=[{'_id': 'r1', 'name': 'Room 1'}])
        m.get('http://recommendation-service:8000/api/recommend?top=5', json={'recommendations': []})
        response = client.get('/')
        assert response.status_code == 200
        assert b'u1' not in response.data
        assert b'Sign in to punch in' in response.data

def test_index_api_error(client):
    with requests_mock.Mocker() as m:
        m.get('http://checkin-service:5000/api/rooms', status_code=500)
        m.get('http://recommendation-service:8000/api/recommend?top=5', status_code=500)
        response = client.get('/')
        assert response.status_code == 200


def test_debug_home_cta_visible(client):
    response = client.get('/debug/home/cta')

    assert response.status_code == 200
    assert b'Punch in' in response.data
    assert b'packed' in response.data
    assert b'quiet' in response.data
    assert b'debug_ll2' not in response.data


def test_debug_home_cta_hidden(client):
    response = client.get('/debug/home/done')

    assert response.status_code == 200
    assert b'Punch in again' in response.data
    assert b'Bobst LL2' in response.data
    assert b'Bobst 9F' in response.data


def test_debug_home_cooldown(client):
    response = client.get('/debug/home/cooldown')

    assert response.status_code == 200
    assert b"You've Punched In Today!" in response.data
    assert b'You are really locked in.' in response.data
    assert b'Punch cooldown' not in response.data


def test_debug_checkin_bypass_cooldown_opens_flow(client, monkeypatch):
    recent_checkin = {
        'room_id': 'bobst_3',
        'time': datetime.now(webapp_module.USER_TIMEZONE).isoformat(),
    }
    monkeypatch.setattr(
        webapp_module,
        '_room_options',
        lambda: ([{'_id': 'bobst_3', 'name': 'Bobst 3F'}], None),
    )
    monkeypatch.setattr(
        webapp_module,
        '_recent_user_checkins',
        lambda user_id: ([recent_checkin], None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/debug/checkin/bypass-cooldown', follow_redirects=True)

    assert response.status_code == 200
    assert b'Bobst 3F' in response.data
    assert b'Punch cooldown active' not in response.data
    with client.session_transaction() as sess:
        assert sess['debug_bypass_checkin_cooldown'] is True


def test_checkin_step1_hides_room_ids_and_last_room(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_room_options',
        lambda: ([{'_id': 'bobst_3', 'name': 'Bobst 3F'}], None),
    )
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/checkin/step1')

    assert response.status_code == 200
    assert b'Bobst 3F' in response.data
    assert b'Last room' not in response.data
    assert b'Last used' not in response.data


def test_checkin_step1_repeat_requires_confirmation(client, monkeypatch):
    rooms = [{'_id': 'bobst_3', 'name': 'Bobst 3F'}]
    old_checkin = {
        'room_id': 'bobst_3',
        'time': (datetime.now(webapp_module.USER_TIMEZONE) - timedelta(minutes=31)).isoformat(),
    }
    monkeypatch.setattr(webapp_module, '_room_options', lambda: (rooms, None))
    monkeypatch.setattr(
        webapp_module,
        '_recent_user_checkins',
        lambda user_id: ([old_checkin], None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/checkin/step1', data={'room_id': 'bobst_3'})

    assert response.status_code == 200
    assert b'Are you sure you returned to Bobst 3F and want to punch in again?' in response.data


def test_checkin_step1_skips_repeat_confirmation_for_different_room(client, monkeypatch):
    rooms = [
        {'_id': 'bobst_3', 'name': 'Bobst 3F'},
        {'_id': 'bobst_ll1', 'name': 'Bobst LL1'},
    ]
    old_checkin = {
        'room_id': 'bobst_ll1',
        'time': (datetime.now(webapp_module.USER_TIMEZONE) - timedelta(minutes=31)).isoformat(),
    }
    monkeypatch.setattr(webapp_module, '_room_options', lambda: (rooms, None))
    monkeypatch.setattr(
        webapp_module,
        '_recent_user_checkins',
        lambda user_id: ([old_checkin], None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/checkin/step1', data={'room_id': 'bobst_3'})

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/checkin/step2')


def test_checkin_hook_plain_punch_success(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_recent_user_checkins',
        lambda user_id: ([{'room_id': 'bobst_3', 'time': '2026-05-04T12:00:00'}], None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}

    response = client.get('/checkin/hook')

    assert response.status_code == 200
    assert b"You've punched in!" in response.data
    assert b'Students helped' not in response.data

def test_checkin_success(client):
    with requests_mock.Mocker() as m:
        m.post('http://checkin-service:5000/api/checkins', status_code=201)
        response = client.post('/checkin', data={'user_id': 'u1', 'room_id': 'r1', 'crowdedness': 3, 'quietness': 3})
        assert response.status_code == 200
        assert b'Checkin successful' in response.data

def test_checkin_fail(client):
    with requests_mock.Mocker() as m:
        m.post('http://checkin-service:5000/api/checkins', status_code=400, text='Bad Request')
        response = client.post('/checkin', data={'room_id': 'r1'})
        assert response.status_code == 200
        assert b'Checkin failed' in response.data

def test_checkin_exception(client):
    with requests_mock.Mocker() as m:
        import requests
        m.post('http://checkin-service:5000/api/checkins', exc=requests.exceptions.ConnectTimeout)
        response = client.post('/checkin', data={'room_id': 'r1'})
        assert response.status_code == 200
        assert b'Error' in response.data


def test_oauth_login_redirects_to_google(client, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/session/oauth/callback')

    response = client.get('/session/login', base_url='http://localhost:3000')

    assert response.status_code == 302
    assert response.location.startswith(webapp_module.AUTH_URL)
    assert 'client_id=client-id' in response.location
    with client.session_transaction() as sess:
        assert sess['oauth_states']


def test_oauth_callback_sets_session(client, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/session/oauth/callback')

    with client.session_transaction() as sess:
        sess['oauth_states'] = ['state-123']

    with requests_mock.Mocker() as m:
        m.post(webapp_module.TOKEN_URL, json={'access_token': 'token'})
        m.get(webapp_module.USERINFO_URL, json={'email': 'person@nyu.edu', 'name': 'Person'})
        response = client.get('/session/oauth/callback?code=abc&state=state-123')

    assert response.status_code == 302
    assert response.location == '/'
    with client.session_transaction() as sess:
        assert sess['user_id'] == 'person@nyu.edu'
        assert sess['user_email'] == 'person@nyu.edu'
        assert sess['user_name'] == 'Person'


def test_oauth_callback_rejects_non_nyu_email(client, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/session/oauth/callback')

    with client.session_transaction() as sess:
        sess['oauth_states'] = ['state-123']

    with requests_mock.Mocker() as m:
        m.post(webapp_module.TOKEN_URL, json={'access_token': 'token'})
        m.get(webapp_module.USERINFO_URL, json={'email': 'person@example.com', 'name': 'Person'})
        response = client.get('/session/oauth/callback?code=abc&state=state-123')

    assert response.status_code == 302
    assert response.location == '/profile'
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_oauth_login_normalizes_to_callback_host(client, monkeypatch):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'client-secret')
    monkeypatch.setenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/session/oauth/callback')

    response = client.get('/session/login', base_url='http://127.0.0.1:3000')

    assert response.status_code == 302
    assert response.location == 'http://localhost:3000/session/login'
