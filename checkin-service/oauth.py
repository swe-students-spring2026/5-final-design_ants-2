import os
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "openid email profile"


def _client_id():
    return os.environ["GOOGLE_CLIENT_ID"]


def _client_secret():
    return os.environ["GOOGLE_CLIENT_SECRET"]


def _redirect_uri():
    return os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:5000/callback")


def generate_login_url():
    csrf_state = os.urandom(16).hex()
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": csrf_state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}", csrf_state


def callback(args, csrf_state):
    if args.get("state") != csrf_state:
        return False, "Wrong csrf_state returned."

    code = args.get("code")
    if not code:
        return False, "Google did not return token code."

    token_resp = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": _client_id(),
            "client_secret": _client_secret(),
            "redirect_uri": _redirect_uri(),
            "grant_type": "authorization_code",
        },
    )
    tokens = token_resp.json()
    access_token = tokens["access_token"]
    user_resp = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    return True, user_resp.json()
