import sqlite3
import os
import datetime
import json

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schedule.db')

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Courses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_str TEXT,
            week_num TEXT,
            date TEXT,
            day INTEGER,
            period INTEGER,
            subject TEXT,
            class_name TEXT,
            raw_text TEXT,
            is_substitute INTEGER DEFAULT 0,
            is_adjusted INTEGER DEFAULT 0,
            adjust_note TEXT DEFAULT "",
            is_period_8 INTEGER DEFAULT 0,
            is_morning_remedial INTEGER DEFAULT 0,
            is_concurrent INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, period)
        )
    ''')
    
    # Check if is_morning_remedial / is_concurrent column exists (for upgrade)
    cursor.execute("PRAGMA table_info(courses)")
    cols = [col['name'] for col in cursor.fetchall()]
    if 'is_morning_remedial' not in cols:
        cursor.execute('ALTER TABLE courses ADD COLUMN is_morning_remedial INTEGER DEFAULT 0')
    if 'is_concurrent' not in cols:
        cursor.execute('ALTER TABLE courses ADD COLUMN is_concurrent INTEGER DEFAULT 0')
    
    # Manual records table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manual_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            period INTEGER DEFAULT 0,
            class_name TEXT DEFAULT "",
            subject TEXT NOT NULL,
            record_type TEXT NOT NULL, -- 'substitute', 'period_8', 'morning_remedial', 'adjusted', 'other'
            amount REAL DEFAULT 0,
            note TEXT DEFAULT "",
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Default settings
    defaults = {
        'substitute_rate': '455',
        'period_8_rate': '540',
        'morning_remedial_rate': '455',
        'concurrent_rate': '455',
        'morning_remedial_days': '1,3,4',
        'morning_remedial_subject': '學習扶助',
        'last_sync_time': '',
        'teacher_name': '施智凱',
        'teacher_no': '154'
    }
    for k, v in defaults.items():
        cursor.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', (k, v))
        
    conn.commit()
    conn.close()

def save_crawled_courses(semester_data):
    conn = get_db()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Read remedial settings
    cursor.execute('SELECT value FROM settings WHERE key="morning_remedial_days"')
    row = cursor.fetchone()
    remedial_days = [int(x.strip()) for x in row['value'].split(',') if x.strip().isdigit()] if row else [1, 3, 4]
    
    cursor.execute('SELECT value FROM settings WHERE key="morning_remedial_subject"')
    row_sub = cursor.fetchone()
    remedial_subject = row_sub['value'] if row_sub else '學習扶助'

    for week_key, w_data in semester_data.items():
        # 1. Insert/Update crawled courses
        for c in w_data['courses']:
            if not c['date']:
                continue
            is_concurrent = 1 if ('(兼)' in (c.get('raw_text') or '') or '(兼)' in (c.get('subject') or '') or '[兼]' in (c.get('raw_text') or '') or c.get('is_concurrent')) else 0
            cursor.execute('''
                INSERT INTO courses (
                    week_str, week_num, date, day, period, subject, class_name,
                    raw_text, is_substitute, is_adjusted, adjust_note, is_period_8, is_morning_remedial, is_concurrent, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, period) DO UPDATE SET
                    week_str=excluded.week_str,
                    week_num=excluded.week_num,
                    day=excluded.day,
                    subject=excluded.subject,
                    class_name=excluded.class_name,
                    raw_text=excluded.raw_text,
                    is_substitute=excluded.is_substitute,
                    is_adjusted=excluded.is_adjusted,
                    adjust_note=excluded.adjust_note,
                    is_period_8=excluded.is_period_8,
                    is_concurrent=excluded.is_concurrent,
                    updated_at=excluded.updated_at
            ''', (
                c['week_str'], c['week_num'], c['date'], c['day'], c['period'],
                c['subject'], c['class_name'], c['raw_text'],
                1 if c['is_substitute'] else 0,
                1 if c['is_adjusted'] else 0,
                c['adjust_note'],
                1 if c['is_period_8'] else 0,
                0,
                is_concurrent,
                now_str
            ))
            
        # 2. Insert Morning Study Remedial Teaching for days in remedial_days (週一、週三、週四 Period 0)
        day_dates = w_data.get('day_dates', {})
        for day in remedial_days:
            if day in day_dates and day_dates[day]:
                d_str = day_dates[day]
                cursor.execute('''
                    INSERT INTO courses (
                        week_str, week_num, date, day, period, subject, class_name,
                        raw_text, is_substitute, is_adjusted, adjust_note, is_period_8, is_morning_remedial, updated_at
                    ) VALUES (?, ?, ?, ?, 0, ?, '全校/自習', ?, 0, 0, '', 0, 1, ?)
                    ON CONFLICT(date, period) DO UPDATE SET
                        subject=excluded.subject,
                        class_name=excluded.class_name,
                        raw_text=excluded.raw_text,
                        is_morning_remedial=1,
                        updated_at=excluded.updated_at
                ''', (
                    w_data['week_str'], w_data['week_num'], d_str, day,
                    remedial_subject, f"{remedial_subject} (早自修)", now_str
                ))

    cursor.execute('UPDATE settings SET value=? WHERE key="last_sync_time"', (now_str,))
    conn.commit()
    conn.close()

def get_setting(key, default=''):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key=?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, str(value)))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized and schema updated.")
