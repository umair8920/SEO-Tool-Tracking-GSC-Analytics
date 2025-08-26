import logging
import requests
from datetime import datetime
import google_auth_oauthlib.flow
import google.oauth2.credentials

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from routes.flash import flash, get_flashed_messages

from db_client import client  # your Mongo client
from .utils import credentials_to_dict  # helper to convert credentials to dict

logger = logging.getLogger(__name__)
router = APIRouter()

# Use your production OAuth credentials file.
CLIENT_SECRETS_FILE = "client_secret.json"
SCOPES = [
    'https://www.googleapis.com/auth/webmasters.readonly',
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile'
]

def validate_credentials(request: Request) -> bool:
    """
    Reconstructs the credentials from session and checks if they have expired.
    Returns True if valid; False otherwise.
    """
    creds_dict = request.state.session.get("credentials")
    if not creds_dict:
        logger.info("No credentials found in session.")
        return False
    try:
        creds = google.oauth2.credentials.Credentials(
            token=creds_dict["token"],
            refresh_token=creds_dict.get("refresh_token"),
            token_uri=creds_dict["token_uri"],
            client_id=creds_dict["client_id"],
            client_secret=creds_dict["client_secret"],
            scopes=creds_dict["scopes"]
        )
        # google.oauth2.credentials.Credentials computes .expired based on its expiry.
        if creds.expired:
            logger.info("Credentials have expired.")
            return False
        return True
    except Exception as e:
        logger.error("Error validating credentials: %s", e, exc_info=True)
        return False

@router.get("/authorize", name="auth_authorize")
def authorize(request: Request):
    """
    Initiates the Google OAuth flow for any public user.
    Users will be redirected to Google's consent screen using your production credentials.
    """
    logger.info("Starting OAuth flow for public authentication")
    try:
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES
        )
        # Dynamically generate the callback URL for OAuth2.
        callback_url = request.url_for("auth_oauth2callback")
        flow.redirect_uri = str(callback_url)

        # Generate the authorization URL and state.
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force re-consent to get refresh token
        )
        # Save the state in the session to prevent CSRF.
        request.state.session['state'] = state
        flash(request, "Redirecting to Google for authentication...", "info")
        logger.info("Redirecting user to Google's OAuth consent screen")
        return RedirectResponse(url=authorization_url)
    except Exception as e:
        logger.error("Error during OAuth authorization: %s", e)
        flash(request, "An error occurred during authentication. Please try again.", "danger")
        return f"Error during authorization: {e}"

@router.get("/oauth2callback", name="auth_oauth2callback")
def oauth2callback(request: Request):
    """
    Handles the Google OAuth callback.
    Exchanges the authorization code for tokens, retrieves user info, and upserts the user in the database.
    This modified flow now accepts any Google user.
    """
    logger.info("Received OAuth2 callback")
    state = request.state.session.get('state')
    if not state:
        logger.error("Missing state in session during callback")
        flash(request, "Session expired or invalid. Please try again.", "danger")
        return "Session state missing. Please try again."
    try:
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            CLIENT_SECRETS_FILE, scopes=SCOPES, state=state
        )
        flow.redirect_uri = str(request.url_for("auth_oauth2callback"))

        # Exchange the authorization code for tokens.
        authorization_response = str(request.url)
        flow.fetch_token(authorization_response=authorization_response)

        credentials = flow.credentials
        request.state.session['credentials'] = credentials_to_dict(credentials)
        logger.info("Successfully obtained and stored OAuth tokens")

        # Fetch user information from Google's UserInfo endpoint.
        userinfo_endpoint = "https://www.googleapis.com/oauth2/v1/userinfo"
        headers = {"Authorization": f"Bearer {credentials.token}"}
        response = requests.get(userinfo_endpoint, headers=headers)
        if response.status_code == 200:
            user_info = response.json()
            logger.info("Fetched user profile: %s", user_info)

            # Save user info in session.
            request.state.session["user_email"] = user_info.get("email")
            request.state.session["user_name"] = user_info.get("name")

            # Upsert the user in the database.
            db = client["apimio"]
            users_coll = db["users"]
            user_email = user_info["email"]
            now = datetime.utcnow()
            users_coll.update_one(
                {"email": user_email},
                {
                    "$set": {
                        "name": user_info.get("name"),
                        "updatedAt": now
                    },
                    "$setOnInsert": {
                        "createdAt": now
                    }
                },
                upsert=True
            )
            logger.info("User record upserted for email: %s", user_email)

            # Retrieve the user document to store the user ID in session.
            found_user = users_coll.find_one({"email": user_email})
            if found_user:
                request.state.session["user_id"] = str(found_user["_id"])
                logger.info("Stored user_id in session: %s", request.state.session["user_id"])
                flash(request, "Login successful! Welcome back.", "success")
            else:
                logger.error("Could not find user after upsert? Email=%s", user_email)
                flash(request, "User authentication failed. Please try again.", "danger")
        else:
            logger.error("Failed to fetch user info: %s", response.text)
            flash(request, "Failed to retrieve your Google profile. Please try again.", "warning")

        # Redirect the user to the dashboard where their registered domains and analytics are shown.
        return RedirectResponse(url=request.url_for("dashboard_sites_list"))
    except Exception as e:
        logger.error("Error during OAuth callback: %s", e)
        flash(request, "Authentication failed. Please try again.", "danger")
        return f"Error during OAuth callback: {e}"


@router.get("/logout", name="auth_logout")
def logout(request: Request):
    """
    Logs out the user by clearing session data and redirecting to the home page.
    """
    try:
        # Clear the session data.
        request.state.session.clear()
        logger.info("User successfully logged out; session cleared.")
        flash(request, "You have been logged out successfully.", "success")
        return RedirectResponse(url="/", status_code=303)
    except Exception as e:
        logger.error("Error during logout: %s", e, exc_info=True)
        flash(request, "An error occurred while logging out. Please try again.", "danger")
        return f"Error during logout: {e}"
