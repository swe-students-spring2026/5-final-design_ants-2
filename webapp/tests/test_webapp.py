import pytest
import requests_mock
from app import app

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

def test_index_api_error(client):
    with requests_mock.Mocker() as m:
        m.get('http://checkin-service:5000/api/rooms', status_code=500)
        m.get('http://recommendation-service:8000/api/recommend?top=5', status_code=500)
        response = client.get('/')
        assert response.status_code == 200

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
