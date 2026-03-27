"""
calendar_tool.py — Google Calendar event creation.

Creates a 1-hour meeting on the user's primary calendar with the
specified attendee and sends invite notifications.
"""

import uuid
from datetime import datetime, timedelta


def create_meeting(calendar_service, emails: list[str], date: str, time: str, title: str = "Meeting", agenda: str = "") -> tuple[str, str]:
    """
    Create a Google Calendar event for multiple attendees and send invites.

    Args:
        calendar_service: Authenticated Google Calendar API service object.
        emails: List of attendee email addresses.
        date: Meeting date in YYYY-MM-DD format.
        time: Meeting start time in HH:MM (24-hour) format.
        title: Meeting title/summary.
        agenda: Meeting agenda for the description.

    Returns:
        tuple (event_id, meet_link).
    """
    # Build start and end times (1-hour duration)
    start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    end_dt = start_dt + timedelta(hours=1)

    timezone = "Asia/Kolkata" # Default for India

    try:
        # Build event body
        event = {
            "summary": title,
            "description": f"Hello,\n\nYou are invited to a meeting scheduled via the Meeting Scheduler Agent.\n\n"
                           f"TIME: {date} at {time}\n"
                           f"AGENDA:\n{agenda}\n\n"
                           f"Note: This invitation includes an official Google Meet link and RSVP buttons.\n\n"
                           f"Best regards,\nMeeting Scheduler Agent",
            "start": {
                "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": timezone,
            },
            "attendees": [{"email": email} for email in emails],
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
            "reminders": {"useDefault": True},
        }

        created_event = (
            calendar_service.events()
            .insert(
                calendarId="primary",
                body=event,
                sendUpdates="all",
                conferenceDataVersion=1,
            )
            .execute()
        )

        event_id = created_event.get("id")
        meet_link = created_event.get("hangoutLink")

        if not meet_link:
            conf_data = created_event.get("conferenceData", {})
            for ep in conf_data.get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri")
                    break
        
        if not meet_link:
            meet_link = "Failed to generate link"

        print(f"[CALENDAR] Meeting created: {event_id} | Link: {meet_link}")
        return event_id, meet_link

    except Exception as e:
        print(f"[CALENDAR] Failed to create meeting: {e}")
        raise


def get_event_status(calendar_service, event_id: str, attendee_email: str) -> str:
    """
    Fetch the attendee's response status for a specific event.

    Args:
        calendar_service: Authenticated Calendar API service.
        event_id: The Google Calendar event ID.
        attendee_email: The attendee's email to check.

    Returns:
        responseStatus (str): One of 'needsAction', 'accepted', 'declined', 'tentative'.
        Returns 'error' if the event or attendee cannot be found.
    """
    try:
        event = (
            calendar_service.events()
            .get(calendarId="primary", eventId=event_id)
            .execute()
        )

        attendees = event.get("attendees", [])
        for attendee in attendees:
            if attendee.get("email", "").lower() == attendee_email.lower():
                status = attendee.get("responseStatus", "needsAction")
                print(f"[CALENDAR] Status for {attendee_email}: {status}")
                return status

    except Exception as e:
        print(f"[CALENDAR] Failed to get event status: {e}")
        return "error"

def delete_event(calendar_service, event_id: str):
    """Delete a Google Calendar event."""
    try:
        calendar_service.events().delete(calendarId="primary", eventId=event_id).execute()
        print(f"[CALENDAR] Meeting cancelled: {event_id}")
        return True
    except Exception as e:
        print(f"[CALENDAR] Failed to cancel meeting {event_id}: {e}")
        return False
