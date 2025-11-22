import os
import time
import logging
from urllib.parse import urlparse
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except Exception:
    psycopg2 = None
    RealDictCursor = None
    PSYCOPG2_AVAILABLE = False
import json

class Database:
    def _mask_db_url(self, u):
        try:
            p = urlparse(u)
            if p.username and p.hostname:
                user = p.username
                host = p.hostname
                port = f":{p.port}" if p.port else ''
                db = p.path.lstrip('/') if p.path else ''
                return f"{p.scheme}://{user}:****@{host}{port}/{db}"
        except Exception:
            pass
        return u
    def __init__(self):
        self.raw_db_url = os.getenv("DATABASE_URL", "")
        # Allow specifying DB components individually if DATABASE_URL is not present
        self.db_user = os.getenv('DB_USER')
        self.db_password = os.getenv('DB_PASSWORD')
        self.db_host = os.getenv('DB_HOST')
        self.db_port = os.getenv('DB_PORT')
        self.db_name = os.getenv('DB_NAME')
        # Choose which connection parameters to use
        if self.raw_db_url:
            self.db_url = self.raw_db_url
        elif self.db_user and self.db_host and self.db_name:
            # Build a DSN to be used by psycopg2
            user = self.db_user
            pwd = self.db_password or ''
            host = self.db_host
            port = self.db_port or '5432'
            name = self.db_name
            # postgres URL
            self.db_url = f"postgresql://{user}:{pwd}@{host}:{port}/{name}"
        else:
            # No DB provided; set to None so we don't attempt to connect with a default 'postgres' user in production
            self.db_url = None
        # Log masked DB URL for debugging, avoid exposing credentials in logs
        if self.db_url:
            logging.info(f"DB URL: { self._mask_db_url(self.db_url) }")
        else:
            logging.info("DB no URL provided; database connection is disabled until configured")
        self.conn = None
        self.mock_config = {}
        self.mock_history = []
        self.mock_schedules = []
        # Connection tuning from env
        try:
            self.db_connect_timeout = int(os.getenv('DB_CONNECT_TIMEOUT', '10'))
        except Exception:
            self.db_connect_timeout = 10
        try:
            self.db_retries = int(os.getenv('DB_RETRIES', '3'))
        except Exception:
            self.db_retries = 3
        try:
            self.db_retry_delay = float(os.getenv('DB_RETRY_DELAY', '2'))
        except Exception:
            self.db_retry_delay = 2.0
        try:
            self.db_log_suppression_seconds = int(os.getenv('DB_LOG_SUPPRESSION_SECONDS', '60'))
        except Exception:
            self.db_log_suppression_seconds = 60
        # runtime tracking for throttled logging
        self._db_last_failed = None
        self._db_unavailable_until = 0
        self._db_last_error = None
        self._db_failure_count = 0
        self.init_db()
        # Optionally validate DB connection at start to early detect auth failures
        validate_on_start = os.getenv('DB_VALIDATE_ON_START', '1').lower() in ('1', 'true', 'yes')
        if validate_on_start:
            conn = self.get_conn()
            if conn:
                logging.info('✅ Database connection valid at startup')
            else:
                logging.info('⚠️ Database unavailable at startup; falling back to mock storage')

    def get_conn(self):
        # If we've marked DB as unavailable until a certain time (throttled), skip attempts
        now_ts = time.time()
        if now_ts < getattr(self, '_db_unavailable_until', 0):
            return None
        if self.conn is None or getattr(self.conn, 'closed', True):
            # Attempt to connect with retries and connect_timeout
            last_err = None
            show_attempt_logs = (self._db_last_failed is None) or (now_ts - (self._db_last_failed or 0) > self.db_log_suppression_seconds)
            for attempt in range(1, max(1, self.db_retries) + 1):
                try:
                    if not PSYCOPG2_AVAILABLE:
                        raise RuntimeError('psycopg2 not available')
                    # Parse the URL into kwargs for psycopg2 to avoid password parsing issues
                    parsed = urlparse(self.db_url)
                    # If the URL uses the postgres scheme, parse appropriately
                    params = {}
                    if parsed.scheme and parsed.scheme.startswith('postgres'):
                        if parsed.username:
                            params['user'] = parsed.username
                        if parsed.password:
                            params['password'] = parsed.password
                        if parsed.hostname:
                            params['host'] = parsed.hostname
                        if parsed.port:
                            params['port'] = parsed.port
                        if parsed.path and len(parsed.path) > 1:
                            params['dbname'] = parsed.path.lstrip('/')
                    else:
                        # Use the raw db_url string if parsing doesn't yield components
                        params['dsn'] = self.db_url
                    # If there are no params, fall back to using the raw DSN
                    if 'user' not in params and 'dsn' not in params:
                        params['dsn'] = self.db_url
                    # pass connect_timeout explicitly
                    params['connect_timeout'] = self.db_connect_timeout
                    # Connect
                    if 'dsn' in params:
                        # Always pass connect_timeout when using dsn string as well
                        self.conn = psycopg2.connect(params['dsn'], connect_timeout=self.db_connect_timeout)
                    else:
                        self.conn = psycopg2.connect(**params)
                    self.conn.autocommit = True
                    return self.conn
                except Exception as e:
                    last_err = e
                    # Log and retry with backoff
                    import logging
                    # Provide a friendlier hint for authentication error
                    msg = str(e)
                    if show_attempt_logs:
                        if 'password authentication failed' in msg or 'authentication failed' in msg:
                            logging.warning(f"Database connect attempt {attempt}/{self.db_retries} failed: authentication error (check DB_USER/DB_PASSWORD or DATABASE_URL).")
                        else:
                            logging.warning(f"Database connect attempt {attempt}/{self.db_retries} failed: {e}")
                    if attempt < self.db_retries:
                        try:
                            time.sleep(self.db_retry_delay)
                        except Exception:
                            pass
                    # increment failure count for exponential backoff
                    self._db_failure_count = max(1, self._db_failure_count + 1)
            # Final fallback - mark connection as None and go to in-memory mock
            import logging
            # Final failure: record and compute a cooldown period to avoid spamming logs
            self._db_last_failed = time.time()
            self._db_last_error = str(last_err)
            # Exponential backoff: 30s, 60s, 120s... capped at 3600s
            backoff = min(3600, 30 * (2 ** max(0, self._db_failure_count - 1)))
            self._db_unavailable_until = self._db_last_failed + backoff
            if show_attempt_logs:
                logging.warning(f"⚠️ Database connection failed after {self.db_retries} attempts ({last_err}); using in-memory mock storage.")
            self.conn = None
        return self.conn

    def force_reconnect(self):
        """Force the database to attempt to reconnect immediately and reset failure counters."""
        self._db_unavailable_until = 0
        self._db_failure_count = 0
        self._db_last_failed = None
        self._db_last_error = None
        return self.get_conn()

    def get_status(self):
        conn = self.conn
        connected = False
        try:
            connected = bool(conn and not getattr(conn, 'closed', True))
        except Exception:
            connected = False
        return {
            'connected': connected,
            'last_error': self._db_last_error,
            'last_failed_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self._db_last_failed)) if self._db_last_failed else None,
            'unavailable_until': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(self._db_unavailable_until)) if self._db_unavailable_until else None,
            'masked_db_url': self._mask_db_url(self.db_url) if hasattr(self, 'db_url') else None
        }

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
