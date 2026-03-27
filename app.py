import os
import uuid
import base64
from datetime import datetime
import threading
import time
from flask import Flask, request, jsonify, render_template, send_from_directory
from dotenv import load_dotenv
from email.mime.text import MIMEText

import database
import llm
import calendar_tool
import followup
from auth import get_calendar_service, get_gmail_service

# Load environment variables
load_dotenv()

import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

app = Flask(__name__, static_folder='static', template_folder='static')
app.config['JSON_SORT_KEYS'] = False

# BASE_URL for Accept/Decline links
# In production, this would be your domain. Locally, it's localhost:5000.
BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")

# --- Helper: Send SaaS Invitation Email ---

def send_invitation_email(gmail_service, meeting_id, participant):
    """Send an HTML invitation email with Accept/Decline buttons."""
    email = participant["email"]
    name = participant["name"]
    
    # Fetch meeting details for the email
    details = database.get_meeting_details(meeting_id)
    meeting = details["meeting"]
    
    print(f"[GMAIL] Preparing invite for {email} with link: {meeting['meet_link']}")
    
    subject = f"Invitation: {meeting['title']} | {meeting['date']}"
    
    agenda_html = "".join([f"<li>{line.strip()}</li>" for line in meeting["agenda"].split("\n") if line.strip()])
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <h2>Hi {name},</h2>
        <p>You are invited to a meeting scheduled as follows:</p>
        <div style="background: #f4f4f4; padding: 15px; border-radius: 8px;">
            <p><strong>Date:</strong> {meeting['date']}</p>
            <p><strong>Time:</strong> {meeting['time']}</p>
            <p><strong>Meet Link:</strong> <a href="{meeting['meet_link']}">{meeting['meet_link']}</a></p>
        </div>
        <h3>Agenda:</h3>
        <ul>{agenda_html}</ul>
        <hr>
        <p>Please respond to the official Google Calendar invitation sent to your inbox.</p>
        <p style="margin-top: 30px; font-size: 0.9em; color: #777;">Best regards,<br>Meeting Scheduler Agent</p>
    </body>
    </html>
    """

    try:
        message = MIMEText(html_body, "html")
        message["to"] = email
        message["subject"] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
        
        gmail_service.users().messages().send(userId="me", body={"raw": raw_message}).execute()
        print(f"[GMAIL] Invitation sent to {email}")
        return True
    except Exception as e:
        print(f"[GMAIL] Failed to send email to {email}: {e}")
        return False

# --- Background Scheduler ---

def process_scheduled_emails():
    """Background thread to process delayed emails/invites."""
    while True:
        try:
            pending_meetings = database.get_pending_scheduled_meetings()
            if pending_meetings:
                # We need a new service instance for the thread
                calendar_service = get_calendar_service()
                
                for m in pending_meetings:
                    emails = [p['email'] for p in m['participants']]
                    print(f"[SCHEDULER] Processing delayed invite for '{m['title']}'")
                    try:
                        event_id, meet_link = calendar_tool.create_meeting(
                            calendar_service,
                            emails=emails,
                            date=m['date'],
                            time=m['time'],
                            title=m['title'],
                            agenda=m['agenda']
                        )
                        database.update_meeting_sent(m['id'], event_id, meet_link)
                        print(f"[SCHEDULER] Successfully sent delayed invite for '{m['title']}'")
                    except Exception as e:
                        print(f"[SCHEDULER] Failed to send delayed invite for {m['id']}: {e}")
        except Exception as e:
            print(f"[SCHEDULER] Error in background loop: {e}")
            
        time.sleep(60) # Check every 60 seconds

def process_followups():
    """Background thread to process pending follow-ups."""
    # Wait a bit before starting so server loads
    time.sleep(10)
    while True:
        try:
            pending_participants = database.get_pending_followups()
            if pending_participants:
                gmail_service = get_gmail_service()
                for p in pending_participants:
                    # Construct meeting dict expected by send_followup_email
                    meeting_data = {
                        "email": p["email"],
                        "name": p["name"],
                        "date": p["date"],
                        "time": p["time"],
                        "meet_link": p["meet_link"],
                        "agenda": p["agenda"],
                        "title": p.get("title", "Meeting")
                    }
                    
                    print(f"[FOLLOWUP] Sending followup #{p['followup_count'] + 1} to {p['email']}")
                    success = followup.send_followup_email(gmail_service, meeting_data, p['followup_count'] + 1)
                    if success:
                        database.increment_followup(p["participant_id"])
                        print(f"[FOLLOWUP] Successfully tracked followup for {p['email']}")
        except Exception as e:
            print(f"[FOLLOWUP] Error in background loop: {e}")
            
        time.sleep(60 * 30) # Check every 30 minutes

threading.Thread(target=process_scheduled_emails, daemon=True).start()
threading.Thread(target=process_followups, daemon=True).start()

# --- API Routes ---

@app.route("/")
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route("/<path:path>")
def static_proxy(path):
    # Send static files from the static folder
    return send_from_directory(app.static_folder, path)

@app.route("/api/summary")
def get_summary():
    return jsonify(database.get_dashboard_summary())

@app.route("/api/meetings")
def get_meetings():
    return jsonify(database.get_all_meetings())

@app.route("/api/users", methods=['GET', 'POST'])
def handle_users():
    if request.method == 'POST':
        data = request.json
        success = database.add_user(data.get('name'), data.get('email'))
        return jsonify({"success": success})
    users = database.get_all_users()
    print(f"[API] Serving {len(users)} users")
    return jsonify(users)

@app.route("/api/users/<email>", methods=['DELETE'])
def remove_user(email):
    success = database.delete_user(email)
    return jsonify({"success": success})

@app.route("/api/sync-responses")
def sync_responses():
    """Sync RSVP statuses from Google Calendar to local DB."""
    try:
        calendar_service = get_calendar_service()
        meetings = database.get_all_meetings()
        
        sync_count = 0
        for m in meetings:
            if not m.get('event_id'): continue
            
            # Get participants for this meeting
            details = database.get_meeting_details(m['id'])
            for p in details['participants']:
                if p['status'] == 'pending':
                    new_status = calendar_tool.get_event_status(calendar_service, m['event_id'], p['email'])
                    # Map Google status to our status
                    if new_status == 'accepted':
                        database.update_participant_status(m['id'], p['email'], 'accepted')
                        sync_count += 1
                    elif new_status == 'declined':
                        database.update_participant_status(m['id'], p['email'], 'declined')
                        sync_count += 1
        
        return jsonify({"success": True, "synced": sync_count})
    except Exception as e:
        print(f"[SYNC] Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/meetings/<int:meeting_id>", methods=["GET", "DELETE"])
def handle_meeting(meeting_id):
    if request.method == "DELETE":
        try:
            details = database.get_meeting_details(meeting_id)
            meeting = details["meeting"]
            
            # 1. Cancel Google Calendar Event
            if meeting.get("event_id"):
                calendar_service = get_calendar_service()
                calendar_tool.delete_event(calendar_service, meeting["event_id"])
            
            # 2. Delete from Database
            success = database.delete_meeting_db(meeting_id)
            return jsonify({"success": success})
        except Exception as e:
            print(f"[API] Delete Error: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
            
    return jsonify(database.get_meeting_details(meeting_id))

@app.route("/api/create-meeting", methods=["POST"])
def create_meeting():
    data = request.json
    title = data.get("title")
    date = data.get("date")
    time = data.get("time")
    agenda = data.get("agenda")
    participants = data.get("participants", [])

    if not all([title, date, time, agenda]) or not participants:
        return jsonify({"error": "Missing meeting details or participants"}), 400
    
    try:
        emails_for_calendar = [p["email"] for p in participants]
        
        send_status = data.get("send_status", "sent")
        scheduled_send_time = data.get("scheduled_send_time")
        
        event_id = None
        meet_link = "Pending (Scheduled for later)"
        
        if send_status == "sent":
            # 1. Create Calendar Event immediately
            calendar_service = get_calendar_service()
            event_id, mock_meet_link = calendar_tool.create_meeting(
                calendar_service,
                emails=emails_for_calendar,
                date=date,
                time=time,
                title=title,
                agenda=agenda
            )
            meet_link = mock_meet_link
        
        # 2. Save to Database
        meeting_id = database.create_meeting_db(
            event_id=event_id,
            title=title,
            date=date,
            time=time,
            meet_link=meet_link,
            agenda=agenda,
            participants=participants,
            send_status=send_status,
            scheduled_send_time=scheduled_send_time
        )
        
        # 3. Send Emails (Disabled to prevent duplicate. Google sends the official invitation automatically.)
        # gmail_service = get_gmail_service()
        # for p in participants:
        #     send_invitation_email(gmail_service, meeting_id, p)
            
        print(f"[API] Meeting '{title}' created with {len(participants)} participants.")
        return jsonify({"success": True, "meeting_id": meeting_id, "meet_link": meet_link})

    except Exception as e:
        print(f"[API] Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/meeting-response")
def handle_response():
    status = request.args.get("status")
    meeting_id = request.args.get("id")
    email = request.args.get("email")
    
    if not all([status, meeting_id, email]):
        return "Invalid response link.", 400
    
    try:
        database.update_participant_status(meeting_id, email, status)
        return render_template('response_confirmation.html', status=status)
    except Exception as e:
        print(f"[API] Response Error: {e}")
        return "Failed to record response.", 500

if __name__ == "__main__":
    # Ensure database is ready
    database.init_db()
    
    print("\n" + "="*60)
    print("SaaS Meeting Scheduler Dashboard is Starting...")
    print("URL: http://127.0.0.1:5000")
    print("="*60 + "\n")
    
    app.run(debug=True, port=5000, host="0.0.0.0")
