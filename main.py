"""
main.py — Main controller for the Meeting Scheduler & Follow-Up Agent.

Interactive loop that:
1. Takes natural language input from the user
2. Extracts meeting details via Gemini LLM
3. Validates and asks for missing fields
4. Creates a Google Calendar event with invite
5. Tracks the meeting for follow-up
6. Runs a background scheduler to send follow-ups
"""

import sys
import threading
import time

from auth import get_calendar_service, get_gmail_service
from llm import extract_meeting_details, validate_meeting_data
from calendar_tool import create_meeting
from followup import add_meeting, check_and_followup, get_pending_count, list_pending_meetings
import database


# ─── Background Scheduler ──────────────────────────────────────────────────────

SCHEDULER_INTERVAL = 3600  # 1 hour in seconds
scheduler_running = False
scheduler_thread = None


def start_scheduler(calendar_service, gmail_service):
    """Start the background follow-up scheduler."""
    global scheduler_running
    scheduler_running = True

    def scheduler_loop():
        while scheduler_running:
            try:
                check_and_followup(calendar_service, gmail_service)
            except Exception as e:
                print(f"\n[SCHEDULER] ❌ Error during follow-up check: {e}")
            # Sleep in small intervals so we can stop quickly
            for _ in range(SCHEDULER_INTERVAL):
                if not scheduler_running:
                    break
                time.sleep(1)

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    print("[SCHEDULER] 🔄 Background follow-up scheduler started (runs every 1 hour).")
    return thread


def stop_scheduler():
    """Stop the background scheduler."""
    global scheduler_running
    scheduler_running = False
    print("[SCHEDULER] ⏹️  Scheduler stopped.")


# ─── Interactive Agent ──────────────────────────────────────────────────────────

def collect_missing_fields(data: dict, missing: list) -> dict:
    """
    Interactively ask the user for any missing required fields.
    """
    for field in missing:
        # Clean up the field name for display
        field_name = field.split(" (")[0]  # Remove format hints

        while True:
            value = input(f"\n⚠️  Missing '{field_name}'. Please enter {field_name}: ").strip()
            if value:
                data[field_name] = value
                break
            print(f"   '{field_name}' is required. Please provide a value.")

    return data


def process_meeting_request(user_input: str, calendar_service, gmail_service):
    """
    Process a single meeting request from user input.
    """
    print("\n" + "=" * 60)
    print("🤖 Processing your request...")
    print("=" * 60)

    # Step 1: Extract details via Gemini
    try:
        data = extract_meeting_details(user_input)
        
        # Database lookup: if email is missing but name is present, try DB
        if not data.get("email") and data.get("name"):
            print(f"[DATABASE] Searching for email for: {data['name']}...")
            db_email = database.get_email_by_name(data["name"])
            if db_email:
                data["email"] = db_email
                print(f"[DATABASE] Found email: {db_email}")
            else:
                print(f"[DATABASE] No email found for {data['name']} in database.")

        print(f"\n[EXTRACTED DATA]")
        print(f"   Name  : {data.get('name', 'N/A')}")
        print(f"   Email : {data.get('email', 'N/A')}")
        print(f"   Date  : {data.get('date', 'N/A')}")
        print(f"   Time  : {data.get('time', 'N/A')}")
        print(f"   Agenda: {data.get('agenda', 'N/A')}")
    except ValueError as e:
        print(f"\n❌ Could not understand your request: {e}")
        print("   Please try again with a clearer message.")
        return

    # Step 2: Validate extracted data
    missing = validate_meeting_data(data)

    if missing:
        print(f"\n⚠️  Missing or invalid fields: {', '.join(missing)}")
        data = collect_missing_fields(data, missing)

        # Re-validate after collecting missing fields
        still_missing = validate_meeting_data(data)
        if still_missing:
            print(f"\n❌ Still missing required fields: {', '.join(still_missing)}")
            return

    # Step 3: Confirm with user
    print(f"\n📅 Ready to schedule meeting:")
    print(f"   Attendee : {data.get('name', '')} <{data['email']}>")
    print(f"   Date     : {data['date']}")
    print(f"   Time     : {data['time']}")
    print(f"   Duration : 1 hour")

    confirm = input("\n✅ Confirm? (y/n): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("   Meeting cancelled.")
        return

    # Step 4: Create the calendar event
    try:
        event_id, meet_link = create_meeting(
            calendar_service,
            email=data["email"],
            date=data["date"],
            time=data["time"],
            agenda=data.get("agenda", ""),
            title=data.get("title", "Meeting"),
        )
    except Exception as e:
        print(f"\n❌ Failed to create meeting: {e}")
        return

    # Step 5: Print Meet Link (TERMINAL OUTPUT - VERY IMPORTANT)
    print("\n" + "*" * 60)
    print(f"🌟 GOOGLE MEET LINK: {meet_link}")
    print("*" * 60)
    print("\n[NOTE] If you don't see the link above, check your Calendar API quota.")

    # Step 6: Display Email Template
    print(f"\n[EMAIL PREVIEW]")
    print(f"Subject: Invitation: {data['title']} | {data['date']}")
    print(f"\nHi {data.get('name', 'there')},")
    print("\nI hope you're doing well.")
    print("\nYou are invited to a meeting scheduled as follows:")
    print(f"\nDate: {data['date']}")
    print(f"Time: {data['time']}")
    print(f"Meeting Link: {meet_link}")
    print("\nAgenda:")
    for point in data['agenda'].split('\n'):
        print(f"- {point.strip()}")
    print("\nPlease confirm your availability.")
    print("\nLooking forward to your participation.")
    print("\nBest regards,")
    print("Scheduler Agent")
    print("=" * 60)

    # Step 7: Add to follow-up tracking
    add_meeting(
        event_id=event_id,
        email=data["email"],
        date=data["date"],
        time=data["time"],
        meet_link=meet_link,
        agenda=data.get("agenda", ""),
        name=data.get("name", ""),
        title=data.get("title", "Meeting"),
    )

    print(f"\n✅ Status: Ready")
    print(f"🎉 Meeting scheduled and tracking started!")


def main():
    """Main entry point for the Meeting Scheduler Agent."""
    print("=" * 60)
    print("  🗓️  Meeting Scheduler & Follow-Up Agent")
    print("=" * 60)
    print()

    # Authenticate and get services
    try:
        print("🔐 Authenticating with Google APIs...")
        calendar_service = get_calendar_service()
        gmail_service = get_gmail_service()
        print("✅ Authentication successful!\n")
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)

    # Start the background scheduler
    start_scheduler(calendar_service, gmail_service)

    # Interactive loop
    print("─" * 60)
    print("Commands:")
    print("  • Type a meeting request (e.g., 'Schedule a meeting with")
    print("    john@example.com on 2026-03-26 at 2 PM')")
    print("  • 'status'  — View pending meetings")
    print("  • 'check'   — Manually trigger follow-up check")
    print("  • 'quit'    — Exit the agent")
    print("─" * 60)

    try:
        while True:
            user_input = input("\n📝 Enter your request: ").strip()

            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ("quit", "exit", "q"):
                print("\n👋 Shutting down...")
                stop_scheduler()
                break

            elif user_input.lower() == "status":
                list_pending_meetings()
                print(f"   Total tracked: {get_pending_count()}")
                continue

            elif user_input.lower() == "check":
                print("\n🔍 Running manual follow-up check...")
                check_and_followup(calendar_service, gmail_service)
                continue

            # Process meeting request
            process_meeting_request(user_input, calendar_service, gmail_service)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted. Shutting down...")
        stop_scheduler()

    print("Goodbye! 👋")


if __name__ == "__main__":
    main()
