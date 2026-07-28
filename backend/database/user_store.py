"""User repository with optional MongoDB persistence.

Mongo is used only when MONGODB_URI is configured and reachable. SQLite is a
development fallback so the application remains usable without credentials.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timezone

from database import db

logger = logging.getLogger("database.users")
_client = None
_users = None


def _mongo_users():
    global _client, _users
    uri = os.getenv("MONGODB_URI", "").strip()
    if not uri:
        return None
    if _users is None:
        try:
            from pymongo import MongoClient
            _client = MongoClient(uri, serverSelectionTimeoutMS=3000)
            _client.admin.command("ping")
            _users = _client[os.getenv("MONGODB_DATABASE", "claimledger")]["users"]
            _users.create_index("username", unique=True)
            logger.info("Using MongoDB for user accounts")
        except Exception as exc:
            logger.error("MongoDB is configured but unavailable: %s", exc)
            raise RuntimeError("MongoDB Atlas is configured but unavailable; fix the connection before signing in or signing up.") from exc
    return _users


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()


def create_user(username, password, role):
    username = username.lower().strip()
    users = _mongo_users()
    if users is None:
        return db.create_user(username, password, role)
    salt = secrets.token_hex(16)
    try:
        users.insert_one({"username": username, "password_hash": _hash(password, salt), "salt": salt,
                          "role": role, "created_at": datetime.now(timezone.utc).isoformat()})
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise ValueError("Username is already registered") from exc
        raise


def authenticate_user(username, password):
    users = _mongo_users()
    if users is None:
        return db.authenticate_user(username, password)
    user = users.find_one({"username": username.lower().strip()})
    if not user or not secrets.compare_digest(_hash(password, user["salt"]), user["password_hash"]):
        return None
    return {"username": user["username"], "role": user["role"]}
