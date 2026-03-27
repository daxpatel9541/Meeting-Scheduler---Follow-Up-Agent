"""
auth.py — OAuth2 authentication for Google Calendar and Gmail APIs.

Handles:
- Loading credentials from credentials.json
- Token refresh / creation via InstalledAppFlow
- Persisting tokens in token.json
- Exposing ready-to-use service objects
"""

import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Scopes required for Calendar + Gmail
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
]

# Paths
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def _get_credentials():
    """Load or create OAuth2 credentials."""
    creds = None

    # Check for existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If no valid credentials, go through the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("[AUTH] Token refreshed successfully.")
            except Exception as e:
                print(f"[AUTH] Token refresh failed: {e}. Re-authenticating...")
                creds = None

        if not creds:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"credentials.json not found at {CREDENTIALS_FILE}. "
                    "Please place your OAuth credentials file in the project directory."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
            print("[AUTH] Authentication successful.")

        # Save the token for future runs
        with open(TOKEN_FILE, "w") as token_file:
            token_file.write(creds.to_json())
            print("[AUTH] Token saved to token.json")

    return creds


def get_calendar_service():
    """Return an authenticated Google Calendar API service."""
    creds = _get_credentials()
    service = build("calendar", "v3", credentials=creds)
    print("[AUTH] Calendar service ready.")
    return service


def get_gmail_service():
    """Return an authenticated Gmail API service."""
    creds = _get_credentials()
    service = build("gmail", "v1", credentials=creds)
    print("[AUTH] Gmail service ready.")
    return service
