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
    assert b"You've Punched In Today!" in response.data
    assert b'You are really locked in.' in response.data
    assert b'Punch in again' not in response.data
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
    monkeypatch.setattr(webapp_module, '_room_options', lambda: (rooms, None))
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    monkeypatch.setattr(webapp_module, '_checked_in_room_today', lambda checkins, room_id: True)
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


def test_session_login_post_redirects_home(client):
    response = client.post('/session/login')
    assert response.status_code == 302
    assert response.location.endswith('/')


def test_session_logout_clears_session(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/session/logout')

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_session_login_without_oauth_config(client, monkeypatch):
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
    monkeypatch.delenv('GOOGLE_REDIRECT_URI', raising=False)

    response = client.get('/session/login', base_url='http://localhost:3000')

    assert response.status_code == 302
    assert response.location.endswith('/profile')


def test_oauth_callback_no_code(client):
    with client.session_transaction() as sess:
        sess['oauth_states'] = ['state-abc']

    response = client.get('/session/oauth/callback?state=state-abc')

    assert response.status_code == 302
    assert response.location.endswith('/profile')


def test_oauth_callback_state_mismatch(client):
    with client.session_transaction() as sess:
        sess['oauth_states'] = ['state-abc']

    response = client.get('/session/oauth/callback?state=wrong&code=x')

    assert response.status_code == 302
    assert response.location.endswith('/profile')


def test_profile_anonymous(client):
    response = client.get('/profile')
    assert response.status_code == 200


def test_profile_signed_in(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_recent_user_checkins',
        lambda user_id: ([{'room_id': 'bobst_3', 'time': '2026-05-04T12:00:00'}], None),
    )
    monkeypatch.setattr(
        webapp_module,
        '_room_options',
        lambda: ([{'_id': 'bobst_3', 'name': 'Bobst 3F'}], None),
    )
    monkeypatch.setattr(webapp_module, '_recommendations', lambda top=3: ([], None))
    monkeypatch.setattr(webapp_module, '_user_profile', lambda user_id: ({'emoji': '\U0001F642'}, None))

    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/profile')
    assert response.status_code == 200


def test_profile_handles_service_errors(client, monkeypatch):
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], 'down'))
    monkeypatch.setattr(webapp_module, '_room_options', lambda: ([], 'down'))
    monkeypatch.setattr(webapp_module, '_recommendations', lambda top=3: ([], 'down'))
    monkeypatch.setattr(webapp_module, '_user_profile', lambda user_id: (None, 'down'))

    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/profile')
    assert response.status_code == 200


def test_profile_emoji_get_requires_signin(client):
    response = client.get('/profile/emoji')
    assert response.status_code == 302
    assert response.location.endswith('/profile')


def test_profile_emoji_get_signed_in(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/profile/emoji')
    assert response.status_code == 200


def test_profile_emoji_post_valid(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_safe_json_put',
        lambda url, payload: (200, {'user': {'emoji': '\U0001F4BF'}}, None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/profile/emoji', data={'emoji': '\U0001F4BF'})

    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess['user_emoji'] == '\U0001F4BF'


def test_profile_emoji_post_invalid(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/profile/emoji', data={'emoji': '   '})

    assert response.status_code == 302
    assert response.location.endswith('/profile/emoji')


def test_profile_emoji_post_handles_service_failure(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_safe_json_put',
        lambda url, payload: (500, None, 'service down'),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/profile/emoji', data={'emoji': '\U0001F4BF'})

    assert response.status_code == 302


def test_checkin_get_redirects_to_step1(client, monkeypatch):
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/checkin')

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_get_redirects_when_not_signed_in(client):
    response = client.get('/checkin')
    assert response.status_code == 302
    assert response.location.endswith('/profile')


def test_checkin_get_redirects_home_during_cooldown(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_checkin_cooldown_state',
        lambda checkins: {'active': True, 'remaining_seconds': 600, 'remaining_minutes': 10, 'last_checkin': None},
    )
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/checkin')

    assert response.status_code == 302
    assert response.location.endswith('/')


def test_checkin_step1_get_renders(client, monkeypatch):
    monkeypatch.setattr(webapp_module, '_room_options', lambda: ([{'_id': 'bobst_3', 'name': 'Bobst 3F'}], None))
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.get('/checkin/step1')
    assert response.status_code == 200


def test_checkin_step1_post_no_room(client, monkeypatch):
    monkeypatch.setattr(webapp_module, '_room_options', lambda: ([], None))
    monkeypatch.setattr(webapp_module, '_recent_user_checkins', lambda user_id: ([], None))
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'

    response = client.post('/checkin/step1', data={'room_id': '   '})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_step2_redirects_when_no_pending(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/step2')
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_step2_get_with_pending(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3'}
    response = client.get('/checkin/step2')
    assert response.status_code == 200


def test_checkin_step2_post_valid(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3'}

    response = client.post('/checkin/step2', data={'crowdedness': '4'})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step3')
    with client.session_transaction() as sess:
        assert sess['pending_checkin']['crowdedness'] == 4


def test_checkin_step2_post_non_integer(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3'}

    response = client.post('/checkin/step2', data={'crowdedness': 'abc'})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step2')


def test_checkin_step3_redirects_without_pending(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/step3')
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_step3_get_with_pending(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3', 'crowdedness': 4}
    response = client.get('/checkin/step3')
    assert response.status_code == 200


def test_checkin_step3_post_success(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_safe_json_post',
        lambda url, payload: (201, {'checkin': {**payload, 'time': '2026-05-04T12:00:00'}}, None),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3', 'crowdedness': 4}

    response = client.post('/checkin/step3', data={'quietness': '3'})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/extra')


def test_checkin_step3_post_cooldown(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_safe_json_post',
        lambda url, payload: (429, None, 'cooldown'),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3', 'crowdedness': 4}

    response = client.post('/checkin/step3', data={'quietness': '3'})

    assert response.status_code == 302
    assert response.location.endswith('/')


def test_checkin_step3_post_failure(client, monkeypatch):
    monkeypatch.setattr(
        webapp_module,
        '_safe_json_post',
        lambda url, payload: (500, None, 'boom'),
    )
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3', 'crowdedness': 4}

    response = client.post('/checkin/step3', data={'quietness': '3'})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_step3_post_invalid_quietness(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['pending_checkin'] = {'room_id': 'bobst_3', 'crowdedness': 4}

    response = client.post('/checkin/step3', data={'quietness': 'abc'})

    assert response.status_code == 302
    assert response.location.endswith('/checkin/step3')


def test_checkin_extra_prompt_redirects_without_last_checkin(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/extra')
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_extra_prompt_get(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.get('/checkin/extra')
    assert response.status_code == 200


def test_checkin_extra_prompt_post_yes(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/extra', data={'answer_more': '1'})
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step4')


def test_checkin_extra_prompt_post_no(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/extra', data={})
    assert response.status_code == 302
    assert response.location.endswith('/checkin/hook')


def test_checkin_hook_redirects_without_checkin(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/hook')
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step1')


def test_checkin_step4_redirects_without_last_checkin(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/step4')
    assert response.status_code == 302


def test_checkin_step4_get(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.get('/checkin/step4')
    assert response.status_code == 200


def test_checkin_step4_post_skip(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/step4', data={'skip': '1'})
    assert response.status_code == 302
    assert response.location.endswith('/checkin/hook')


def test_checkin_step4_post_submit(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/step4', data={'temperature': 'cold'})
    assert response.status_code == 302
    assert response.location.endswith('/checkin/step5')
    with client.session_transaction() as sess:
        assert sess['optional_feedback']['temperature'] == 'cold'


def test_checkin_step5_redirects_without_last_checkin(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
    response = client.get('/checkin/step5')
    assert response.status_code == 302


def test_checkin_step5_get(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.get('/checkin/step5')
    assert response.status_code == 200


def test_checkin_step5_post_skip(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/step5', data={'skip': '1'})
    assert response.status_code == 302
    assert response.location.endswith('/checkin/hook')


def test_checkin_step5_post_submit(client):
    with client.session_transaction() as sess:
        sess['user_id'] = 'person@nyu.edu'
        sess['last_checkin'] = {'room_id': 'bobst_3'}
    response = client.post('/checkin/step5', data={'outlets': 'few'})
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess['optional_feedback']['outlets'] == 'few'


def test_fallback_url_branches():
    assert webapp_module._fallback_url('http://checkin-service:5000/api/x').startswith('http://localhost:5000')
    assert webapp_module._fallback_url('http://checkin-service/api/x').startswith('http://localhost')
    assert webapp_module._fallback_url('http://recommendation-service:8000/api/x').startswith('http://localhost:8000')
    assert webapp_module._fallback_url('http://recommendation-service/api/x').startswith('http://localhost')
    assert webapp_module._fallback_url('http://example.com/api') is None


def test_is_nyu_email_branches():
    assert webapp_module._is_nyu_email('p@nyu.edu') is True
    assert webapp_module._is_nyu_email('p@stern.nyu.edu') is True
    assert webapp_module._is_nyu_email('p@example.com') is False
    assert webapp_module._is_nyu_email('not-an-email') is False
    assert webapp_module._is_nyu_email('') is False


def test_clean_emoji_branches():
    assert webapp_module._clean_emoji('\U0001F642') == '\U0001F642'
    assert webapp_module._clean_emoji('   ') is None
    assert webapp_module._clean_emoji('x' * 50) is None
    assert webapp_module._clean_emoji(123) is None
