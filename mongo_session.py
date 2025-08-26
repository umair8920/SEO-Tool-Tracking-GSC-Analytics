import uuid
from datetime import datetime, timedelta
from typing import Optional

import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

# Import your existing Mongo client from db_client.py
from db_client import client

logger = logging.getLogger(__name__)

# Store sessions in the "fastapi_sessions" collection
db = client["apimio"]
session_collection = db["fastapi_sessions"]

# Name of the cookie for session ID
SESSION_COOKIE_NAME = "session_id"

# How long before a session expires (e.g. 7 days)
SESSION_LIFETIME_DAYS = 7


def create_session_doc(session_id: str) -> dict:
    """Create a new session doc in Mongo with empty data."""
    now = datetime.utcnow()
    expires_at = now + timedelta(days=SESSION_LIFETIME_DAYS)
    doc = {
        "_id": session_id,
        "data": {},
        "expiresAt": expires_at
    }
    try:
        session_collection.insert_one(doc)
        logger.info("Created new session document for session_id: %s", session_id)
    except Exception as e:
        logger.error("Error creating session document: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not create session")
    return doc


def get_session_doc(session_id: str) -> Optional[dict]:
    """Fetch existing session doc from Mongo, or None if not found/expired."""
    try:
        doc = session_collection.find_one({"_id": session_id})
    except Exception as e:
        logger.error("Error retrieving session document for session_id %s: %s", session_id, e, exc_info=True)
        return None

    if not doc:
        logger.info("Session document not found for session_id: %s", session_id)
        return None
    if "expiresAt" in doc and doc["expiresAt"] < datetime.utcnow():
        # Session expired; remove it from the collection.
        try:
            session_collection.delete_one({"_id": session_id})
            logger.info("Deleted expired session for session_id: %s", session_id)
        except Exception as e:
            logger.error("Error deleting expired session for session_id %s: %s", session_id, e, exc_info=True)
        return None
    return doc


def save_session_doc(session_id: str, data: dict):
    """Update session doc with new data and reset expiry."""
    now = datetime.utcnow()
    expires_at = now + timedelta(days=SESSION_LIFETIME_DAYS)
    try:
        session_collection.update_one(
            {"_id": session_id},
            {"$set": {"data": data, "expiresAt": expires_at}},
            upsert=True
        )
        logger.info("Session document updated for session_id: %s", session_id)
    except Exception as e:
        logger.error("Error saving session document for session_id %s: %s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Could not save session")


class MongoSessionMiddleware(BaseHTTPMiddleware):
    """
    Custom middleware that:
      1. Reads session_id from the cookie.
      2. Loads or creates a session document in Mongo.
      3. Places the session data into request.state.session (a dict).
      4. After the response, saves session data back to Mongo.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        # 1. Read session_id from cookie.
        session_id = request.cookies.get(SESSION_COOKIE_NAME)

        # 2. If missing or invalid, create a new session document.
        if not session_id:
            session_id = str(uuid.uuid4())
            try:
                create_session_doc(session_id)
                session_data = {}
            except Exception as e:
                logger.error("Failed to create session: %s", e, exc_info=True)
                raise HTTPException(status_code=500, detail="Session creation failed")
        else:
            # Load session from the database.
            doc = get_session_doc(session_id)
            if doc is None:
                session_id = str(uuid.uuid4())
                try:
                    create_session_doc(session_id)
                    session_data = {}
                except Exception as e:
                    logger.error("Failed to create new session after invalid session found: %s", e, exc_info=True)
                    raise HTTPException(status_code=500, detail="Session creation failed")
            else:
                session_data = doc.get("data", {})

        # 3. Attach the session data and session_id to request.state.
        request.state.session = session_data
        request.state._session_id = session_id

        # 4. Process the request.
        response = await call_next(request)

        # 5. Save the updated session back to Mongo.
        updated_data = request.state.session
        try:
            save_session_doc(session_id, updated_data)
        except Exception as e:
            logger.error("Failed to save session document for session_id %s: %s", session_id, e, exc_info=True)
            # Optionally, you could modify the response to indicate session save failure.

        # 6. Ensure the session_id cookie is set.
        if request.cookies.get(SESSION_COOKIE_NAME) != session_id:
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=session_id,
                max_age=SESSION_LIFETIME_DAYS * 24 * 60 * 60,
                httponly=True,
                samesite="lax",
                secure=False  # Set to True if using HTTPS.
            )

        return response
