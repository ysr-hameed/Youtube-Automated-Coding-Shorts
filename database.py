import os
import psycopg2
from psycopg2.extras import RealDictCursor
import json

class Database:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/vidgen")
        self.conn = None
        self.mock_config = {}
        self.mock_history = []
        self.mock_schedules = []
        self.init_db()

    def get_conn(self):
        if self.conn is None or getattr(self.conn, 'closed', True):
            try:
                self.conn = psycopg2.connect(self.db_url)
                self.conn.autocommit = True
            except Exception as e:
                # Fallback to mock storage when DB unavailable
                print(f"⚠️ Database connection failed ({e}); using in‑memory mock storage.")
                self.conn = None
        return self.conn

    def init_db(self):
        conn = self.get_conn()
        if not conn:
            # No real DB – nothing to initialise
            return
        with conn.cursor() as cur:
            # Config Table (for tokens, client secrets)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
            """)
            # Content History Table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS content_history (
                    id SERIAL PRIMARY KEY,
                    topic TEXT NOT NULL,
                    question TEXT NOT NULL,
                    code TEXT NOT NULL,
                    title TEXT,
                    tags TEXT[],
                    uploaded BOOLEAN DEFAULT FALSE,
                    youtube_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Ensure columns exist for uploaded and youtube_id (safe for migrations)
            cur.execute("ALTER TABLE content_history ADD COLUMN IF NOT EXISTS uploaded BOOLEAN DEFAULT FALSE;")
            cur.execute("ALTER TABLE content_history ADD COLUMN IF NOT EXISTS youtube_id TEXT;")
            print("✅ Database Schema Initialized")

            # Scheduled Runs table - store planned schedule for daily runs
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id SERIAL PRIMARY KEY,
                    scheduled_at TIMESTAMP NOT NULL,
                    executed BOOLEAN DEFAULT FALSE,
                    executed_at TIMESTAMP,
                    result JSON,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

    # --- Config Methods ---
    def set_config(self, key, value):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO app_config (key, value)
                    VALUES (%s, %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """, (key, value))
        else:
            self.mock_config[key] = value

    def get_config(self, key):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM app_config WHERE key = %s", (key,))
                res = cur.fetchone()
                return res[0] if res else None
        else:
            return self.mock_config.get(key)

    # --- History Methods ---
    def add_history(self, content):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO content_history (topic, question, code, title, tags, uploaded, youtube_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    content['topic'],
                    content['question'],
                    content['code'],
                    content.get('title'),
                    content.get('tags', []),
                    content.get('uploaded', False),
                    content.get('youtube_id', None)
                ))
                try:
                    new_id = cur.fetchone()[0]
                except Exception:
                    new_id = None
                return new_id
        else:
            # Append content to mock history and return a generated id
            entry = content.copy()
            entry_id = len(self.mock_history) + 1
            entry['id'] = entry_id
            entry.setdefault('uploaded', False)
            entry.setdefault('youtube_id', None)
            self.mock_history.append(entry)
            return entry_id

    # --- Schedule Methods ---
    def add_schedule(self, scheduled_at):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO schedules (scheduled_at) VALUES (%s) RETURNING id", (scheduled_at,))
                try:
                    new_id = cur.fetchone()[0]
                except Exception:
                    new_id = None
                return new_id
        else:
            # Mock schedule
            entry = {
                'id': len(self.mock_schedules) + 1,
                'scheduled_at': scheduled_at,
                'executed': False,
            }
            self.mock_schedules.append(entry)
            return entry['id']

    def get_schedule_for_day(self, date):
        conn = self.get_conn()
        if conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id, scheduled_at, executed, executed_at, result FROM schedules WHERE date_trunc('day', scheduled_at) = date_trunc('day', %s) ORDER BY scheduled_at", (date,))
                return cur.fetchall()
        else:
            # Filter mock history entries
            from datetime import datetime
            result = []
            for e in self.mock_schedules:
                if isinstance(e.get('scheduled_at'), str):
                    d = datetime.fromisoformat(e['scheduled_at'])
                else:
                    d = e.get('scheduled_at')
                if d and d.date() == date.date():
                    result.append({
                        'id': e.get('id'),
                        'scheduled_at': d,
                        'executed': e.get('executed', False),
                        'executed_at': e.get('executed_at'),
                        'result': e.get('result')
                    })
            return result

    def mark_schedule_executed(self, schedule_id, executed_at=None, result=None):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE schedules SET executed = TRUE, executed_at = %s, result = %s WHERE id = %s", (executed_at, json.dumps(result) if result else None, schedule_id))
                return True
        else:
            for e in self.mock_schedules:
                if e.get('id') == schedule_id:
                    e['executed'] = True
                    e['executed_at'] = executed_at
                    e['result'] = result
                    return True
            return False

    def get_recent_topics(self, limit=50):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT topic FROM content_history ORDER BY created_at DESC LIMIT %s", (limit,))
                return [row[0] for row in cur.fetchall()]
        else:
            # Return most recent topics from mock history
            return [c['topic'] for c in self.mock_history[-limit:][::-1]]

    def get_today_upload_count(self):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM content_history WHERE created_at >= date_trunc('day', now()) AND uploaded = TRUE")
                return cur.fetchone()[0]
        else:
            # Fallback: count 'uploaded' items in mock_history
            return sum(1 for e in (self.mock_history or []) if e.get('uploaded'))

    def mark_uploaded(self, topic=None, entry_id=None, youtube_id=None):
        conn = self.get_conn()
        if not conn:
            # Try to mark in mock history
            if entry_id:
                for e in self.mock_history:
                    if e.get('id') == entry_id:
                        e['uploaded'] = True
                        e['youtube_id'] = youtube_id
                        return True
                return False
            elif topic:
                for e in reversed(self.mock_history):
                    if e.get('topic') == topic:
                        e['uploaded'] = True
                        e['youtube_id'] = youtube_id
                        return True
                return False
            return False
        with conn.cursor() as cur:
            if entry_id:
                cur.execute("UPDATE content_history SET uploaded = TRUE, youtube_id = %s WHERE id = %s", (youtube_id, entry_id))
                return True
            elif topic:
                cur.execute("UPDATE content_history SET uploaded = TRUE, youtube_id = %s WHERE id = (SELECT id FROM content_history WHERE topic = %s ORDER BY created_at DESC LIMIT 1)", (youtube_id, topic))
                return True
        return False

# Instantiate a global db object for importers
db = Database()
