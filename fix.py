import re

with open('database.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = re.compile(r'def get_pending_followups\(\):.*?return pending\n*', re.DOTALL)

new_func = """def get_pending_followups():
    \"\"\"Fetch participants who need a follow-up email.\"\"\"
    import sqlite3
    conn = sqlite3.connect('scheduler.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    from datetime import datetime, timedelta
    now_dt = datetime.now()
    now_str = now_dt.strftime('%Y-%m-%d %H:%M')
    
    cursor.execute('''
        SELECT p.id as participant_id, p.*, m.title, m.date, m.time, m.meet_link, m.agenda, m.created_at
        FROM participants p
        JOIN meetings m ON p.meeting_id = m.id
        WHERE p.status = 'pending' 
        AND p.followup_count < 3
        AND m.send_status = 'sent'
        AND m.date || ' ' || m.time >= ? 
    ''', (now_str,))
    
    results = cursor.fetchall()
    pending = []
    
    for r in results:
        # Parse created_at safely
        try:
            created_at_raw = r['created_at']
            if created_at_raw and len(created_at_raw) >= 19:
                created_at_dt = datetime.strptime(created_at_raw[:19], '%Y-%m-%d %H:%M:%S')
            else:
                created_at_dt = now_dt
        except:
            created_at_dt = now_dt
            
        last_followup = None
        if r['last_followup_time']:
            try:
                last_followup = datetime.strptime(r['last_followup_time'][:19], '%Y-%m-%d %H:%M:%S')
            except:
                pass
                
        threshold = None
        if r['followup_count'] == 0:
            threshold = created_at_dt + timedelta(hours=2)
        else:
            if last_followup:
                threshold = last_followup + timedelta(hours=24)
                
        if threshold and now_dt >= threshold:
            pending.append(dict(r))
            
    conn.close()
    return pending

"""

new_text = pattern.sub(new_func, text)

with open('database.py', 'w', encoding='utf-8') as f:
    f.write(new_text)

print('Reverted database.py')
