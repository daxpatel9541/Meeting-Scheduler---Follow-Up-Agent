"""
llm.py — Gemini-based extraction of meeting details from natural language.

Uses the google-generativeai SDK to prompt Gemini and parse structured JSON
containing: name, email, date (YYYY-MM-DD), time (HH:MM).
"""

import json
import os
import re

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini keys
def _get_api_keys():
    keys = []
    i = 1
    while True:
        key = os.getenv(f"GEMINI_API_KEY_{i}")
        if not key:
            # Also check the old legacy key if no numbered keys exist yet
            if i == 1:
                legacy_key = os.getenv("GEMINI_API_KEY")
                if legacy_key:
                    keys.append(legacy_key)
            break
        keys.append(key)
        i += 1
    return keys

API_KEYS = _get_api_keys()
if not API_KEYS:
    raise EnvironmentError("No GEMINI_API_KEY_* found. Set them in your .env file.")

# Global state for current key index
_current_key_index = 0

def _configure_genai():
    global _current_key_index
    genai.configure(api_key=API_KEYS[_current_key_index])

_configure_genai()

# Use Gemini 2.5 Flash model
MODEL_NAME = "gemini-2.5-flash"

# System prompt for extraction
EXTRACTION_PROMPT = """You are a SaaS Meeting Scheduler Assistant.
Extract meeting details from the user's message.

Rules:
- Return ONLY valid JSON.
- If multiple names/emails are mentioned, put them in the 'name' field separated by commas.
- Format 'date' as YYYY-MM-DD.
- Format 'time' as HH:MM (24-hour).
- 'agenda' is required.
- Provide a 'title' field: a short (3-6 words), professional summary of the meeting based on the agenda.

Example JSON:
{
  "name": "Ishan, Bhumit",
  "email": "",
  "date": "2026-03-26",
  "time": "14:00",
  "agenda": "Point 1\\nPoint 2",
  "title": "Project Alpha Strategy Sync"
}
"""


def extract_meeting_details(user_input: str) -> dict:
    """Send user input to Gemini and extract meeting details as a dict."""
    global _current_key_index
    
    for attempt in range(len(API_KEYS)):
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            prompt = f"{EXTRACTION_PROMPT}\n\nUser message: {user_input}"
            response = model.generate_content(prompt)
            
            raw_text = response.text.strip()
            print(f"[LLM] Raw response: {raw_text}")

            json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found")

            data = json.loads(json_match.group())

            # Ensure expected keys
            for key in ["name", "email", "date", "time", "agenda", "title"]:
                if key not in data:
                    data[key] = ""
            
            return data

        except exceptions.ResourceExhausted:
            _current_key_index = (_current_key_index + 1) % len(API_KEYS)
            genai.configure(api_key=API_KEYS[_current_key_index])
            continue
        except Exception as e:
            if attempt == len(API_KEYS) - 1:
                raise ValueError(f"Failed to extract details: {e}")
            _current_key_index = (_current_key_index + 1) % len(API_KEYS)
            _configure_genai()
            continue


def validate_meeting_data(data: dict) -> list:
    """
    Validate extracted meeting data. Returns a list of missing required fields.
    """
    missing = []

    # Email is mandatory
    if not data.get("email") or not _is_valid_email(data["email"]):
        missing.append("email")

    # Date is required
    if not data.get("date"):
        missing.append("date")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", data["date"]):
        missing.append("date (invalid format, use YYYY-MM-DD)")

    # Time is required
    if not data.get("time"):
        missing.append("time")
    elif not re.match(r"^\d{2}:\d{2}$", data["time"]):
        missing.append("time (invalid format, use HH:MM)")

    # Agenda is required
    if not data.get("agenda") or not data["agenda"].strip():
        missing.append("agenda")

    return missing


def _is_valid_email(email: str) -> bool:
    """Basic email format validation."""
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))
