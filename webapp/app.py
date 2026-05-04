import os
from datetime import datetime
from urllib import error, parse, request

from flask import Flask, flash, redirect, render_template, request as flask_request, session, url_for

CHECKIN_SERVICE_URL = os.getenv("CHECKIN_API", os.getenv("CHECKIN_SERVICE_URL", "http://checkin-service:5000"))
RECOMMENDATION_SERVICE_URL = os.getenv("RECOMMENDATION_API", os.getenv("RECOMMENDATION_SERVICE_URL", "http://recommendation-service:8000"))


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "wireframe-dev-secret")


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


def _room_options():
    ok, data, err = _safe_json_get(f"{CHECKIN_SERVICE_URL}/api/rooms")
    if not ok:
        return [], err
    return data or [], None


def _recent_user_checkins(user_id):
    ok, data, err = _safe_json_get(f"{CHECKIN_SERVICE_URL}/api/checkins/{user_id}")
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
        sample_user_ids=["u1", "u2", "u3", "u4"],
        rooms=rooms,
        recommendations=recommendations,
        current_year=datetime.utcnow().year,
    )


@app.route("/session/login", methods=["POST"])
def session_login():
    user_id = flask_request.form.get("user_id", "").strip()
    if not user_id:
        flash("Select a user before signing in.")
        return redirect(url_for("home"))

    session["user_id"] = user_id
    session.setdefault("session_streak", 0)
    flash(f"Signed in as {user_id}.")
    return redirect(url_for("home"))


@app.route("/session/logout", methods=["POST"])
def session_logout():
    session.clear()
    flash("Signed out.")
    return redirect(url_for("home"))


@app.route("/checkin")
def checkin():
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
        flash("Optional details captured for UX wireframe.")
        return redirect(url_for("profile"))

    return render_template("checkin_step5_outlets.html", user_id=_signed_in_user())


@app.route("/profile")
def profile():
    user_id = _signed_in_user()
    if not user_id:
        return render_template(
            "profile.html",
            user_id=None,
            sample_user_ids=["u1", "u2", "u3", "u4"],
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
        checkins=checkins,
        recommendations=recommendations,
        session_streak=session_streak,
        optional_feedback=session.get("optional_feedback", {}),
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)