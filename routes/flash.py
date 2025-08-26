from fastapi import Request
from typing import List

FLASH_SESSION_KEY = "flash_messages"

def flash(request: Request, message: str, category: str = "info"):
    """
    Stores a flash message in the session.
    """
    if not hasattr(request.state, "session") or request.state.session is None:
        raise RuntimeError("Session middleware is not properly configured.")
    
    session = request.state.session

    flash_messages = session.get(FLASH_SESSION_KEY, [])
    flash_messages.append({"message": message, "category": category})
    
    session[FLASH_SESSION_KEY] = flash_messages  # Update session storage

def get_flashed_messages(request: Request) -> List[dict]:
    """
    Retrieves and clears flash messages from the session.
    """
    if not hasattr(request.state, "session") or request.state.session is None:
        raise RuntimeError("Session middleware is not properly configured.")
    
    session = request.state.session

    messages = session.get(FLASH_SESSION_KEY, [])
    session[FLASH_SESSION_KEY] = []  # Clear messages after retrieval

    return messages if messages else []  # Ensure an empty list is returned
