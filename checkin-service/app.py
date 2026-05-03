import os
from flask import Flask
from dotenv import load_dotenv
from routes import bp
from db import rooms_collection

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)

    seed_rooms()

    return app


def seed_rooms():
    """
    Seed starter room data for local development.
    Later, when using Docker + production MongoDB,
    this can be replaced by a dedicated init script.
    """
    if rooms_collection.count_documents({}) == 0:
        rooms_collection.insert_many([
            {
                "_id": "bobst_ll1",
                "name": "Bobst LL1",
                "current_crowd": None,
                "current_quiet": None,
                "last_updated": None
            },
            {
                "_id": "bobst_2",
                "name": "Bobst 2nd Floor",
                "current_crowd": None,
                "current_quiet": None,
                "last_updated": None
            },
            {
                "_id": "bobst_3",
                "name": "Bobst 3rd Floor",
                "current_crowd": None,
                "current_quiet": None,
                "last_updated": None
            },
            {
                "_id": "bobst_4",
                "name": "Bobst 4th Floor",
                "current_crowd": None,
                "current_quiet": None,
                "last_updated": None
            },
        ])


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=True)