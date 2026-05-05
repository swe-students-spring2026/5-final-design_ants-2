import os
from datetime import datetime
from urllib import error, parse, request

import requests
from flask import Flask, flash, redirect, render_template, request as flask_request, session, url_for

CHECKIN_SERVICE_URL = os.getenv("CHECKIN_API", os.getenv("CHECKIN_SERVICE_URL", "http://checkin-service:5000"))
RECOMMENDATION_SERVICE_URL = os.getenv("RECOMMENDATION_API", os.getenv("RECOMMENDATION_SERVICE_URL", "http://recommendation-service:8000"))
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
SCOPES = "openid email profile"
DEFAULT_REDIRECT_URI = "http://localhost:3000/session/oauth/callback"
OAUTH_STATE_LIMIT = 8


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "wireframe-dev-secret")


class OAuthConfigError(RuntimeError):
    pass


def _oauth_is_configured():
    return bool(os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"))


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise OAuthConfigError(f"{name} is not configured.")
    return value


def _oauth_redirect_uri():
    return os.getenv("GOOGLE_REDIRECT_URI", DEFAULT_REDIRECT_URI)


def _oauth_callback_base_url():
    parsed_uri = parse.urlparse(_oauth_redirect_uri())
    if parsed_uri.scheme and parsed_uri.netloc:
        return f"{parsed_uri.scheme}://{parsed_uri.netloc}"
    return None


def _oauth_generate_login_url(csrf_state):
    params = {
        "client_id": _required_env("GOOGLE_CLIENT_ID"),
        "redirect_uri": _oauth_redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "state": csrf_state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{parse.urlencode(params)}"


def _oauth_callback(args):
    code = args.get("code")
    if not code:
        return False, "Google did not return a token code."

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": _required_env("GOOGLE_CLIENT_ID"),
                "client_secret": _required_env("GOOGLE_CLIENT_SECRET"),
                "redirect_uri": _oauth_redirect_uri(),
                "grant_type": "authorization_code",
            },
            timeout=8,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        user_response = requests.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=8,
        )
        user_response.raise_for_status()
        return True, user_response.json()
    except (KeyError, requests.RequestException, OAuthConfigError) as exc:
        return False, str(exc)


def _remember_oauth_state(csrf_state):
    states = session.get("oauth_states", [])
    if isinstance(states, str):
        states = [states]
    states.append(csrf_state)
    session["oauth_states"] = states[-OAUTH_STATE_LIMIT:]


def _consume_oauth_state(returned_state):
    states = session.get("oauth_states", [])
    if isinstance(states, str):
        states = [states]

    legacy_state = session.pop("oauth_state", None)
    if legacy_state:
        states.append(legacy_state)

    if returned_state not in states:
        session["oauth_states"] = states[-OAUTH_STATE_LIMIT:]
        return False

    states.remove(returned_state)
    session["oauth_states"] = states[-OAUTH_STATE_LIMIT:]
    return True


def _is_nyu_email(email):
    if not email or "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return domain == "nyu.edu" or domain.endswith(".nyu.edu")


def _safe_json_get(url):
    fallback_url = _fallback_url(url)
    try:
        with request.urlopen(url, timeout=4) as response:
            body = response.read().decode("utf-8")
            return True, __import__("json").loads(body), None
    except error.URLError as exc:
        if fallback_url:
            try:
                with request.urlopen(fallback_url, timeout=4) as response:
                    body = response.read().decode("utf-8")
                    return True, __import__("json").loads(body), None
            except Exception:
                pass
        return False, None, str(exc)
    except Exception as exc:  # pragma: no cover - defensive for malformed payloads
        return False, None, str(exc)


def _safe_json_post(url, payload):
    fallback_url = _fallback_url(url)
    data = __import__("json").dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=4) as response:
            body = response.read().decode("utf-8")
            return response.getcode(), __import__("json").loads(body), None
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8") if exc.fp else ""
        return exc.code, None, detail or str(exc)
    except error.URLError as exc:
        if fallback_url:
            fallback_req = request.Request(
                fallback_url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with request.urlopen(fallback_req, timeout=4) as response:
                    body = response.read().decode("utf-8")
                    return response.getcode(), __import__("json").loads(body), None
            except error.HTTPError as fallback_exc:
                detail = (
                    fallback_exc.read().decode("utf-8") if fallback_exc.fp else ""
                )
                return fallback_exc.code, None, detail or str(fallback_exc)
            except Exception:
                pass
        return None, None, str(exc)


def _fallback_url(url):
    if "checkin-service:5000" in url:
        return url.replace("checkin-service:5000", "localhost:5000")
    if "checkin-service" in url:
        return url.replace("checkin-service", "localhost")
    if "recommendation-service:8000" in url:
        return url.replace("recommendation-service:8000", "localhost:8000")
    if "recommendation-service" in url:
        return url.replace("recommendation-service", "localhost")
    return None


def _signed_in_user():
    return session.get("user_id")


def _signed_in_name():
    return session.get("user_name")


def _room_options():
    ok, data, err = _safe_json_get(f"{CHECKIN_SERVICE_URL}/api/rooms")
    if not ok:
        return [], err
    return data or [], None


def _recent_user_checkins(user_id):
    encoded_user_id = parse.quote(str(user_id), safe="")
    ok, data, err = _safe_json_get(f"{CHECKIN_SERVICE_URL}/api/checkins/{encoded_user_id}")
    if not ok:
        return [], err
    return data or [], None


def _recommendations(top=3):
    ok, data, err = _safe_json_get(
        f"{RECOMMENDATION_SERVICE_URL}/api/recommend?{parse.urlencode({'top': top})}"
    )
    if not ok:
        return [], err
    return data.get("recommendations", []), None


def _require_signin():
    if _signed_in_user():
        return None
    flash("Please sign in before punching in.")
    return redirect(url_for("profile"))


@app.route("/")
def home():
    user_id = _signed_in_user()
    rooms, rooms_error = _room_options()
    if rooms_error:
        flash("Unable to fetch live room data from checkin-service.")

    recommendations, recs_error = _recommendations(top=5)
    if recs_error:
        flash("Unable to fetch recommendations from recommendation-service.")

    return render_template(
        "home.html",
        user_id=user_id,
        user_name=_signed_in_name(),
        oauth_ready=_oauth_is_configured(),
        rooms=rooms,
        recommendations=recommendations,
        current_year=datetime.utcnow().year,
    )


@app.route("/session/login", methods=["GET", "POST"])
def session_login():
    if flask_request.method == "POST":
        flash("Use Google sign-in.")
        return redirect(url_for("home"))

    callback_base_url = _oauth_callback_base_url()
    current_base_url = flask_request.host_url.rstrip("/")
    if callback_base_url and callback_base_url != current_base_url:
        return redirect(f"{callback_base_url}{url_for('session_login')}")

    csrf_state = os.urandom(16).hex()
    _remember_oauth_state(csrf_state)
    try:
        return redirect(_oauth_generate_login_url(csrf_state))
    except OAuthConfigError as exc:
        session.pop("oauth_states", None)
        flash(str(exc))
        return redirect(url_for("profile"))


@app.route("/session/oauth/callback")
def session_oauth_callback():
    returned_state = flask_request.args.get("state")
    if not _consume_oauth_state(returned_state):
        flash("Sign-in failed: Wrong OAuth state returned. Start sign-in again from the same Lockin tab.")
        return redirect(url_for("profile"))

    ok, result = _oauth_callback(flask_request.args)
    if not ok:
        flash(f"Sign-in failed: {result}")
        return redirect(url_for("profile"))

    email = (result.get("email") or "").strip()
    if not _is_nyu_email(email):
        flash("Sign-in failed: use an NYU email.")
        return redirect(url_for("profile"))

    user_id = email or result.get("id") or result.get("sub")
    if not user_id:
        flash("Sign-in failed: Google did not return an account id.")
        return redirect(url_for("profile"))

    session["user_id"] = user_id
    session["user_email"] = email
    session["user_name"] = result.get("name") or email or user_id
    session.setdefault("session_streak", 0)
    flash("Signed in.")
    return redirect(url_for("home"))


@app.route("/session/logout", methods=["POST"])
def session_logout():
    session.clear()
    flash("Signed out.")
    return redirect(url_for("home"))


@app.route("/checkin", methods=["GET", "POST"])
def checkin():
    if flask_request.method == "POST":
        payload = {
            "user_id": flask_request.form.get("user_id") or _signed_in_user() or "",
            "room_id": flask_request.form.get("room_id", "").strip(),
            "crowdedness": flask_request.form.get("crowdedness"),
            "quietness": flask_request.form.get("quietness"),
        }
        try:
            response = requests.post(
                f"{CHECKIN_SERVICE_URL}/api/checkins",
                json=payload,
                timeout=4,
            )
        except requests.RequestException as exc:
            return f"Error: {exc}", 200

        if response.status_code == 201:
            return "Checkin successful", 200

        detail = response.text.strip()
        if detail:
            return f"Checkin failed: {detail}", 200
        return "Checkin failed", 200

    gate = _require_signin()
    if gate:
        return gate
    return redirect(url_for("checkin_step1"))


@app.route("/checkin/step1", methods=["GET", "POST"])
def checkin_step1():
    gate = _require_signin()
    if gate:
        return gate

    user_id = _signed_in_user()
    rooms, rooms_error = _room_options()
    if rooms_error:
        flash("Unable to fetch room options right now.")

    recent_checkins, _ = _recent_user_checkins(user_id)
    smart_default_room = recent_checkins[0].get("room_id") if recent_checkins else None

    if flask_request.method == "POST":
        chosen_room = flask_request.form.get("room_id", "").strip()
        if not chosen_room:
            flash("Pick a location to continue.")
            return redirect(url_for("checkin_step1"))

        session["pending_checkin"] = {"room_id": chosen_room}
        return redirect(url_for("checkin_step2"))

    return render_template(
        "checkin_step1_location.html",
        user_id=user_id,
        rooms=rooms,
        smart_default_room=smart_default_room,
    )


@app.route("/checkin/step2", methods=["GET", "POST"])
def checkin_step2():
    gate = _require_signin()
    if gate:
        return gate

    pending = session.get("pending_checkin") or {}
    if not pending.get("room_id"):
        flash("Start with location first.")
        return redirect(url_for("checkin_step1"))

    if flask_request.method == "POST":
        crowdedness_raw = flask_request.form.get("crowdedness")
        try:
            crowdedness = int(crowdedness_raw)
        except (TypeError, ValueError):
            flash("Choose a crowd level to continue.")
            return redirect(url_for("checkin_step2"))

        pending["crowdedness"] = crowdedness
        session["pending_checkin"] = pending
        return redirect(url_for("checkin_step3"))

    return render_template("checkin_step2_crowd.html", user_id=_signed_in_user())


@app.route("/checkin/step3", methods=["GET", "POST"])
def checkin_step3():
    gate = _require_signin()
    if gate:
        return gate

    pending = session.get("pending_checkin") or {}
    if not pending.get("room_id") or not pending.get("crowdedness"):
        flash("Complete previous steps first.")
        return redirect(url_for("checkin_step1"))

    if flask_request.method == "POST":
        quietness_raw = flask_request.form.get("quietness")
        try:
            quietness = int(quietness_raw)
        except (TypeError, ValueError):
            flash("Choose a noise level to continue.")
            return redirect(url_for("checkin_step3"))

        payload = {
            "user_id": _signed_in_user(),
            "room_id": pending["room_id"],
            "crowdedness": pending["crowdedness"],
            "quietness": quietness,
        }
        status_code, response_data, error_text = _safe_json_post(
            f"{CHECKIN_SERVICE_URL}/api/checkins", payload
        )
        if status_code != 201:
            flash("Mandatory check-in submission failed. Please retry.")
            if error_text:
                flash(f"Details: {error_text}")
            return redirect(url_for("checkin_step1"))

        session["last_checkin"] = response_data.get("checkin", payload)
        session["session_streak"] = int(session.get("session_streak", 0)) + 1
        session.pop("pending_checkin", None)
        return redirect(url_for("checkin_hook"))

    return render_template("checkin_step3_quiet.html", user_id=_signed_in_user())


@app.route("/checkin/hook")
def checkin_hook():
    gate = _require_signin()
    if gate:
        return gate

    checkin_data = session.get("last_checkin")
    if not checkin_data:
        flash("No recent check-in found.")
        return redirect(url_for("checkin_step1"))

    # TODO: Replace this mocked impact number with analytics-driven impact metrics.
    impact_number = 142
    return render_template(
        "checkin_hook.html",
        user_id=_signed_in_user(),
        checkin_data=checkin_data,
        impact_number=impact_number,
    )


@app.route("/checkin/step4", methods=["GET", "POST"])
def checkin_step4_optional_temperature():
    gate = _require_signin()
    if gate:
        return gate

    if not session.get("last_checkin"):
        flash("Complete a check-in first.")
        return redirect(url_for("checkin_step1"))

    if flask_request.method == "POST":
        if flask_request.form.get("skip") == "1":
            return redirect(url_for("profile"))

        temp_value = flask_request.form.get("temperature", "").strip()
        optional_feedback = session.get("optional_feedback", {})
        optional_feedback["temperature"] = temp_value
        session["optional_feedback"] = optional_feedback
        return redirect(url_for("checkin_step5_optional_outlets"))

    return render_template("checkin_step4_temp.html", user_id=_signed_in_user())


@app.route("/checkin/step5", methods=["GET", "POST"])
def checkin_step5_optional_outlets():
    gate = _require_signin()
    if gate:
        return gate

    if not session.get("last_checkin"):
        flash("Complete a check-in first.")
        return redirect(url_for("checkin_step1"))

    if flask_request.method == "POST":
        if flask_request.form.get("skip") == "1":
            return redirect(url_for("profile"))

        outlet_value = flask_request.form.get("outlets", "").strip()
        optional_feedback = session.get("optional_feedback", {})
        optional_feedback["outlets"] = outlet_value
        session["optional_feedback"] = optional_feedback

        # TODO: Persist optional Phase 3 upsell fields once backend schema supports them.
        flash("Details saved.")
        return redirect(url_for("profile"))

    return render_template("checkin_step5_outlets.html", user_id=_signed_in_user())


@app.route("/profile")
def profile():
    user_id = _signed_in_user()
    if not user_id:
        return render_template(
            "profile.html",
            user_id=None,
            user_name=None,
            oauth_ready=_oauth_is_configured(),
            checkins=[],
            recommendations=[],
            session_streak=0,
            optional_feedback={},
        )
    checkins, checkins_error = _recent_user_checkins(user_id)
    recommendations, recs_error = _recommendations(top=3)

    if checkins_error:
        flash("Unable to load personal history right now.")
    if recs_error:
        flash("Unable to load recommendations right now.")

    # TODO: Replace session-only streak with a persistent backend user streak.
    session_streak = int(session.get("session_streak", 0))

    return render_template(
        "profile.html",
        user_id=user_id,
        user_name=_signed_in_name(),
        oauth_ready=_oauth_is_configured(),
        checkins=checkins,
        recommendations=recommendations,
        session_streak=session_streak,
        optional_feedback=session.get("optional_feedback", {}),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
