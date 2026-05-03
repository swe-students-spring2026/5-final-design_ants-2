import os
import requests
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv()

CLIENT_ID = os.environ["GOOGLE_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:5000/callback")
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "openid email profile"

def generate_login_url():
    # Generates a login URL for redirecting users to Google OAuth. 
    # Make sure to save csrf_state - it will be checked in callback().
    csrf_state = os.urandom(16).hex()
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "state": csrf_state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}", csrf_state

def callback(args, csrf_state):
    '''
    Input: 
        request.args, 
        csrf_state from previous generate_login_url().
    Output: 
        success (True/False)
        data:
            if success == True:
                {"name": str, "email": str}
            if success == False:
                ErrorMessage: str
    
    Could take a while since there's a roundtrip to google.
    '''

    if args.get("state") != csrf_state:
        return False, "Wrong csrf_state returned."
    code = args.get("code")
    if not code:
        return False, "Google did not return token code."
    
    token_resp = requests.post(TOKEN_URL, data={
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    tokens = token_resp.json()
    access_token = tokens["access_token"]
    user_resp = requests.get(USERINFO_URL, headers={
        "Authorization": f"Bearer {access_token}"
    })
    user_info = user_resp.json()
    return True, user_info