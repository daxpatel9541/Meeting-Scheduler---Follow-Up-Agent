import sqlite3
import os
from datetime import datetime

DB_PATH = "scheduler.db"

def init_db():
    """Initialize the SQLite database and create the SaaS-level tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE
        )
    ''')
    
    # 2. Meetings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            meet_link TEXT,
            agenda TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. Participants table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- pending, accepted, declined
            FOREIGN KEY (meeting_id) REFERENCES meetings (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"[DATABASE] Database refactored at {DB_PATH}")

def populate_initial_users():
    """Add initial users to the database."""
    users = [
        ("Ishan", "ishan.yiion@gmail.com"),
        ("Bhumit", "bhumitryiion@gmail.com")
    ]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany('INSERT OR IGNORE INTO users (name, email) VALUES (?, ?)', users)
    conn.commit()
    conn.close()
    print("[DATABASE] Initial users populated.")

# Helper functions for the Dashboard

def create_meeting_db(event_id, title, date, time, meet_link, agenda, participants):
    """
    Save a new meeting and its participants to the database.
    
    participants: list of dicts [{"name": "...", "email": "..."}]
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Insert meeting
        cursor.execute('''
            INSERT INTO meetings (event_id, title, date, time, meet_link, agenda)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (event_id, title, date, time, meet_link, agenda))
        
        meeting_id = cursor.lastrowid
        
        # Insert participants
        participant_data = [(meeting_id, p["name"], p["email"]) for p in participants]
        cursor.executemany('''
            INSERT INTO participants (meeting_id, name, email)
            VALUES (?, ?, ?)
        ''', participant_data)
        
        conn.commit()
        return meeting_id
    except Exception as e:
        print(f"[DATABASE] Error creating meeting: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def update_participant_status(meeting_id, email, status):
    """Update a specific participant's response status."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE participants 
        SET status = ? 
        WHERE meeting_id = ? AND email = ?
    ''', (status, meeting_id, email))
    conn.commit()
    conn.close()

def get_dashboard_summary():
    """Fetch high-level stats for the dashboard overview cards."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total meetings
    cursor.execute('SELECT COUNT(*) FROM meetings')
    total = cursor.fetchone()[0]
    
    # Get all meetings and their status based on participants
    cursor.execute('''
        SELECT m.id, m.date, m.time,
        CASE 
            WHEN EXISTS (SELECT 1 FROM participants p WHERE p.meeting_id = m.id AND p.status = 'declined') THEN 'declined'
            WHEN NOT EXISTS (SELECT 1 FROM participants p WHERE p.meeting_id = m.id AND p.status != 'accepted') THEN 'accepted'
            ELSE 'pending'
        END as status
        FROM meetings m
    ''')
    rows = cursor.fetchall()
    
    accepted = sum(1 for r in rows if r[3] == 'accepted')
    declined = sum(1 for r in rows if r[3] == 'declined')
    
    # Upcoming: compare date and time against now
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    upcoming = 0
    for r in rows:
        meeting_dt = f"{r[1]} {r[2]}"
        if meeting_dt >= now_str:
            upcoming += 1
            
    conn.close()
    return {
        "total": total,
        "accepted": accepted,
        "declined": declined,
        "upcoming": upcoming
    }

def get_all_meetings():
    """Fetch all meetings with participant summaries for the table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT m.*, 
        (SELECT GROUP_CONCAT(name || ' (' || status || ')') FROM participants p WHERE p.meeting_id = m.id) as participants_summary,
        CASE 
            WHEN EXISTS (SELECT 1 FROM participants p WHERE p.meeting_id = m.id AND p.status = 'declined') THEN 'declined'
            WHEN NOT EXISTS (SELECT 1 FROM participants p WHERE p.meeting_id = m.id AND p.status != 'accepted') THEN 'accepted'
            ELSE 'pending'
        END as status
        FROM meetings m
        ORDER BY m.date DESC, m.time DESC
    ''')
    meetings = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return meetings

def get_meeting_details(meeting_id):
    """Fetch full details of a specific meeting including all participants."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
    meeting = dict(cursor.fetchone())
    
    cursor.execute('SELECT * FROM participants WHERE meeting_id = ?', (meeting_id,))
    participants = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    return {"meeting": meeting, "participants": participants}

def get_email_by_name(name):
    """Utility to resolve name to email from users table."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT email FROM users WHERE LOWER(name) = LOWER(?)', (name.strip(),))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def get_all_users():
    """Fetch all registered users."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY name ASC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def add_user(name, email):
    """Add a new user to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (name, email) VALUES (?, ?)', (name, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_user(email):
    """Delete a user by email."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE email = ?', (email,))
    conn.commit()
    conn.close()
    return True

def delete_meeting_db(meeting_id):
    """Delete a meeting and its participants from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM participants WHERE meeting_id = ?', (meeting_id,))
        cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"[DATABASE] Error deleting meeting {meeting_id}: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    populate_initial_users()
