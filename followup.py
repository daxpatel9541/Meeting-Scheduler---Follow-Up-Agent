"""
followup.py — Follow-up tracking and automated email reminders.

Manages an in-memory list of pending meetings, checks attendee response
status periodically, and sends follow-up emails via Gmail API.

Follow-up rules:
- First follow-up: 2 hours after meeting creation
- Subsequent follow-ups: 24 hours apart
- Maximum 3 follow-ups per meeting
- Stop if attendee accepts or declines
"""

import base64
from datetime import datetime, timedelta
from email.mime.text import MIMEText

from calendar_tool import get_event_status

# In-memory store for pending meetings (no database)
pending_meetings = []


def add_meeting(event_id: str, email: str, date: str, time: str, meet_link: str, agenda: str, name: str = "", **kwargs):
    """
    Add a newly created meeting to the follow-up tracking list.

    Args:
        event_id: Google Calendar event ID.
        email: Attendee's email address.
        date: Meeting date.
        time: Meeting time.
        meet_link: Google Meet link.
        agenda: Meeting agenda.
        name: Attendee name.
    """
    meeting = {
        "event_id": event_id,
        "email": email,
        "name": name,
        "date": date,
        "time": time,
        "meet_link": meet_link,
        "agenda": agenda,
        "title": kwargs.get("title", "Meeting"),
        "followup_count": 0,
        "created_time": datetime.now(),
        "last_followup_time": None,
        "status": "needsAction",
    }
    pending_meetings.append(meeting)
    print(f"[FOLLOWUP] 📋 Tracking meeting {event_id} for {email}")


def check_and_followup(calendar_service, gmail_service):
    """
    Check all pending meetings and send follow-ups if needed.

    This function is called by the scheduler every hour.
    """
    if not pending_meetings:
        print("[FOLLOWUP] No pending meetings to check.")
        return

    print(f"\n[FOLLOWUP] ⏰ Checking {len(pending_meetings)} pending meeting(s)...")

    # Iterate over a copy so we can modify the list safely
    meetings_to_remove = []

    for meeting in pending_meetings:
        event_id = meeting["event_id"]
        email = meeting["email"]
        followup_count = meeting["followup_count"]

        print(f"\n[FOLLOWUP] Checking: {email} (event: {event_id}, follow-ups sent: {followup_count})")

        # Check attendee response status
        status = get_event_status(calendar_service, event_id, email)

        if status in ("accepted", "declined"):
            print(f"[FOLLOWUP] ✅ {email} has {status} the meeting. Stopping follow-ups.")
            meetings_to_remove.append(meeting)
            continue

        if status == "error":
            print(f"[FOLLOWUP] ⚠️ Could not check status for {email}. Skipping this cycle.")
            continue

        # Status is 'needsAction' — check if follow-up is due
        if followup_count >= 3:
            print(f"[FOLLOWUP] 🛑 Max follow-ups (3) reached for {email}. Stopping.")
            meetings_to_remove.append(meeting)
            continue

        now = datetime.now()

        if followup_count == 0:
            # First follow-up: 2 hours after creation
            threshold = meeting["created_time"] + timedelta(hours=2)
        else:
            # Subsequent follow-ups: 24 hours after last follow-up
            threshold = meeting["last_followup_time"] + timedelta(hours=24)

        if now >= threshold:
            # Time to send a follow-up
            print(f"[FOLLOWUP] 📧 Sending follow-up #{followup_count + 1} to {email}...")
            success = send_followup_email(gmail_service, meeting, followup_count + 1)

            if success:
                meeting["followup_count"] += 1
                meeting["last_followup_time"] = now
                print(f"[FOLLOWUP] ✅ Follow-up #{meeting['followup_count']} sent to {email}")
            else:
                print(f"[FOLLOWUP] ❌ Failed to send follow-up to {email}")
        else:
            remaining = threshold - now
            print(f"[FOLLOWUP] ⏳ Next follow-up for {email} in {remaining}")

    # Remove completed meetings
    for meeting in meetings_to_remove:
        pending_meetings.remove(meeting)


def send_followup_email(gmail_service, meeting: dict, followup_number: int) -> bool:
    """
    Send a follow-up reminder email via Gmail API using the standardized template.

    Args:
        gmail_service: Authenticated Gmail API service.
        meeting: Dictionary containing meeting details.
        followup_number: Which follow-up this is (1, 2, or 3).

    Returns:
        True if email sent successfully, False otherwise.
    """
    to_email = meeting["email"]
    name = meeting.get("name") or "there"
    date = meeting["date"]
    time = meeting["time"]
    meet_link = meeting["meet_link"]
    agenda = meeting["agenda"]

    title = meeting.get("title") or "Meeting"
    
    if followup_number == 1:
        subject = f"Gentle Reminder: Invitation to {title} for {date}"
    elif followup_number == 2:
        subject = f"Following up: {title} | RSVP Requested for {date}"
    else:
        subject = f"Final Reminder: Discussion regarding {title} - {date}"

    agenda_formatted = "\n".join([f"- {line.strip()}" for line in agenda.split("\n") if line.strip()])

    body = (
        f"Hi {name},\n\n"
        f"I hope you're doing well.\n\n"
        f"Just following up on the meeting invite sent to you (Follow-up #{followup_number}/3).\n"
        f"You are invited to a meeting scheduled as follows:\n\n"
        f"📅 Date: {date}\n"
        f"⏰ Time: {time}\n"
        f"📍 Meeting Link: {meet_link}\n\n"
        f"Agenda:\n"
        f"{agenda_formatted}\n\n"
        f"Please confirm your availability.\n\n"
        f"Looking forward to your participation.\n\n"
        f"Best regards,\n"
        f"Scheduler Agent"
    )

    try:
        message = MIMEText(body)
        message["to"] = to_email
        message["subject"] = subject

        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        sent_message = (
            gmail_service.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

        print(f"[GMAIL] ✅ Email sent to {to_email} (Message ID: {sent_message.get('id')})")
        return True

    except Exception as e:
        print(f"[GMAIL] ❌ Failed to send email to {to_email}: {e}")
        return False


def get_pending_count() -> int:
    """Return the number of meetings currently being tracked."""
    return len(pending_meetings)


def list_pending_meetings():
    """Print all pending meetings for debugging/status."""
    if not pending_meetings:
        print("[FOLLOWUP] No pending meetings.")
        return

    print(f"\n[FOLLOWUP] 📋 {len(pending_meetings)} pending meeting(s):")
    for i, m in enumerate(pending_meetings, 1):
        print(f"  {i}. {m['email']} | Event: {m['event_id'][:12]}... | "
              f"Follow-ups: {m['followup_count']}/3 | "
              f"Created: {m['created_time'].strftime('%Y-%m-%d %H:%M')}")
