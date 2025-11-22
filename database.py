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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("✅ Database Schema Initialized")

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
                    INSERT INTO content_history (topic, question, code, title, tags)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    content['topic'],
                    content['question'],
                    content['code'],
                    content['title'],
                    content.get('tags', [])
                ))
        else:
            self.mock_history.append(content)

    def get_recent_topics(self, limit=50):
        conn = self.get_conn()
        if conn:
            with conn.cursor() as cur:
                cur.execute("SELECT topic FROM content_history ORDER BY created_at DESC LIMIT %s", (limit,))
                return [row[0] for row in cur.fetchall()]
        else:
            # Return most recent topics from mock history
            return [c['topic'] for c in self.mock_history[-limit:][::-1]]

# Instantiate a global db object for importers
db = Database()


from psycopg2.extras import RealDictCursor
import json

class Database:
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/vidgen")
        self.conn = None
        self.init_db()

    def get_conn(self):
        if self.conn is None or self.conn.closed:
            try:
                self.conn = psycopg2.connect(self.db_url)
                self.conn.autocommit = True
            except Exception as e:
                print(f"❌ Database connection failed: {e}")
                return None
        return self.conn

    def init_db(self):
        conn = self.get_conn()
        if not conn: return
        
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("✅ Database Schema Initialized")

    # --- Config Methods ---
    def set_config(self, key, value):
        conn = self.get_conn()
        if not conn: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO app_config (key, value) 
                VALUES (%s, %s) 
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
            """, (key, value))

    def get_config(self, key):
        conn = self.get_conn()
        if not conn: return None
        with conn.cursor() as cur:
            cur.execute("SELECT value FROM app_config WHERE key = %s", (key,))
            res = cur.fetchone()
            return res[0] if res else None

    # --- History Methods ---
    def add_history(self, content):
        conn = self.get_conn()
        if not conn: return
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO content_history (topic, question, code, title, tags)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                content['topic'], 
                content['question'], 
                content['code'], 
                content['title'], 
                content.get('tags', [])
            ))

    def get_recent_topics(self, limit=50):
        conn = self.get_conn()
        if not conn: return []
        with conn.cursor() as cur:
            cur.execute("SELECT topic FROM content_history ORDER BY created_at DESC LIMIT %s", (limit,))
            return [row[0] for row in cur.fetchall()]

db = Database()
