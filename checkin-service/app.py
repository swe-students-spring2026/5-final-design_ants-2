import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load .env before importing anything that reads env vars (db.db caches MONGO_URI at import time).


from flask import Flask  # noqa: E402
from dotenv import load_dotenv
from routes import bp  # noqa: E402
from db.seed_data import seed_rooms  # noqa: E402


load_dotenv()


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)

    seed_rooms()

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)