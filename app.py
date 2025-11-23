from flask import Flask, render_template, request, jsonify, send_file, redirect
import logging
from flask_cors import CORS
import warnings
# Suppress noisy SyntaxWarning emitted from pydub internals in production
# This prevents messages like "invalid escape sequence '\('" from appearing in logs.
warnings.filterwarnings("ignore", category=SyntaxWarning, module="pydub.utils")
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
from publisher import process_and_upload
from database import db
import threading
import os
from datetime import datetime
import pytz

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv()

from flask_cors import CORS
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
import threading
import os
from datetime import datetime

app = Flask(__name__, static_folder='static', static_url_path='/static')
CORS(app)

generator = ShortsVideoGenerator()
logging.info(f"Audio enabled: {generator.audio_enabled}")
content_mgr = ContentManager()
youtube_mgr = YouTubeManager()
# Start scheduler in production (Render sets RENDER env var)
if os.getenv('RENDER'):
    from scheduler_service import AutoScheduler
    scheduler = AutoScheduler()
    count = int(os.getenv('DAILY_SCHEDULES', '1'))
    scheduler._generate_daily_schedule(count)
    scheduler_thread = threading.Thread(target=scheduler.start, daemon=True)
    scheduler_thread.start()
if not generator.audio_enabled:
    logging.info("⚠️ Audio features are disabled. Ensure pydub is installed and ffmpeg is on PATH for full audio functionality.")

# Optionally start scheduler in background
if os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true':
    try:
        from scheduler_service import AutoScheduler
        scheduler = AutoScheduler()
        # Generate schedule immediately to ensure the UI will show today's schedules
        try:
            count = int(os.getenv('DAILY_SCHEDULES', '1'))
        except Exception:
            count = 1
        scheduler._generate_daily_schedule(count)
        t = threading.Thread(target=scheduler.start, daemon=True)
        t.start()
        logging.info('Scheduler started in background')
    except Exception as e:
        logging.warning(f'Failed to start scheduler in background: {e}')

# Optionally attempt DB connect after server start to avoid initial network/DNS availability issues
if os.getenv('DB_CONNECT_AFTER_START', 'true').lower() in ('1', 'true', 'yes'):
    def _delayed_db_connect():
        try:
            delay = int(os.getenv('DB_CONNECT_AFTER_START_DELAY', '10'))
        except Exception:
            delay = 10
        import time as _t
        _t.sleep(delay)
        try:
            conn = db.get_conn()
            logging.info('Background DB connect attempted; connected=%s', bool(conn))
        except Exception as e:
            logging.warning(f'Background DB connect failed: {e}')
    try:
        threading.Thread(target=_delayed_db_connect, daemon=True).start()
    except Exception:
        pass

@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.json
    
    # Manual Generation
    question = data.get('question')
    code = data.get('code')
    cursor_style = data.get('cursor_style', '_')
    
    generator.cursor_style = cursor_style
    
    try:
        # Build content object similar to AI-generated content so we store a record
        content = {
            'topic': question[:80],
            'question': question,
            'code': code,
            'title': f"{question[:50]} #shorts #coding",
            'description': question,
            'tags': ["shorts", "coding"]
        }
        # Save to DB and generate
        entry_id = db.add_history(content)
        content['db_id'] = entry_id
        auto_upload = data.get('auto_upload', True)
        result = process_and_upload(content, generator, youtube_mgr, filename_prefix='manual', auto_upload=auto_upload)
        video_path = result.get('video_path')
        if not result.get('success'):
            return jsonify({"success": False, "error": result.get('error', 'Generation failed')}), 500
        uploaded = result.get('uploaded', False)
        video_id = result.get('youtube_id')
        upload_error = result.get('upload_error')

        return jsonify({
            "success": True,
            "video_url": f"/api/download/{os.path.basename(video_path)}",
            "uploaded": uploaded,
            "youtube_id": video_id,
            "upload_error": upload_error
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ai/generate', methods=['POST'])
def ai_generate():
    try:
        print("Starting AI content generation")
        # Generate content using Gemini
        data = request.json or {}
        auto_upload = data.get('auto_upload', True)
        content = content_mgr.generate_content()
        print(f"AI content generated: {content}")
        
        # Process generation and optional upload through helper
        result = process_and_upload(content, generator, youtube_mgr, filename_prefix='ai', auto_upload=auto_upload)
        if not result.get('success'):
            print(f"Generation failed: {result.get('error')}")
            return jsonify({"success": False, "error": result.get('error', 'Generation failed')}), 500
        video_path = result.get('video_path')
        print(f"Video generated at: {video_path}")

        # The upload was handled inside process_and_upload; use results
        uploaded = result.get('uploaded', False)
        video_id = result.get('youtube_id')
        upload_error = result.get('upload_error')

        return jsonify({
            "success": True,
            "content": content,
            "video_url": f"/api/download/{os.path.basename(video_path)}",
            "uploaded": result.get('uploaded'),
            "youtube_id": result.get('youtube_id'),
            "upload_error": result.get('upload_error')
        })
    except Exception as e:
        # Return helpful error info to frontend (do not expose sensitive traces)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/download/<filename>')
def download(filename):
    return send_file(os.path.join("output", filename), as_attachment=False)

@app.route('/api/auth/youtube', methods=['POST'])
def auth_youtube():
    try:
        success = youtube_mgr.authenticate()
        if isinstance(success, str):
            return jsonify({"success": False, "auth_url": success})
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/youtube/callback')
def auth_callback():
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        if not code or not state:
            return "Missing code or state", 400
        
        saved_state = db.get_config('oauth_state')
        if state != saved_state:
            return "Invalid state", 400
        
        client_config = youtube_mgr._get_client_secrets()
        if not client_config:
            return "No client config", 500
        
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8080/")
        flow = Flow.from_client_config(client_config, scopes=youtube_mgr.SCOPES, redirect_uri=redirect_uri)
        flow.fetch_token(code=code)
        creds = flow.credentials
        youtube_mgr._save_credentials(creds)
        youtube_mgr.youtube = build(youtube_mgr.api_service_name, youtube_mgr.api_version, credentials=creds)
        return redirect('/')
    except Exception as e:
        return f"Authentication failed: {str(e)}", 500


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    try:
        return jsonify({"authenticated": youtube_mgr.is_authenticated()})
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)})


@app.route('/api/health', methods=['GET'])
def health():
    try:
        status = {"ok": True, "audio_enabled": generator.audio_enabled}
        try:
            status['db'] = db.get_status()
        except Exception as e:
            status['db'] = {'connected': False, 'error': str(e)}
        return jsonify(status)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/db/reconnect', methods=['POST'])
def db_reconnect():
    try:
        db.force_reconnect()
        return jsonify({'success': True, 'message': 'Reconnection attempted (check /api/health for status)'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/cron/generate', methods=['GET'])
def cron_generate():
    # Optional secret for security
    secret_env = os.getenv('CRON_SECRET')
    secret_param = request.args.get('secret')
    if secret_env and secret_param != secret_env:
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    # Determine count to generate and daily limit
    try:
        count = int(request.args.get('count', '1'))
    except Exception:
        count = 1

    try:
        daily_limit = int(os.getenv('DAILY_UPLOAD_LIMIT', '1'))
    except Exception:
        daily_limit = 1

    results = []
    for _ in range(count):
        # Check how many we've uploaded today
        uploaded_today = db.get_today_upload_count() or 0
        if uploaded_today >= daily_limit:
            results.append({"success": False, "error": "Daily upload limit reached"})
            break

        content = content_mgr.generate_content()
        if not content:
            results.append({"success": False, "error": "AI generation failed/skipped"})
            continue

        entry_id = content.get('db_id')
        result = process_and_upload(content, generator, youtube_mgr, filename_prefix='cron', auto_upload=True)
        results.append(result)
    return jsonify({"success": True, "count": len(results), "results": results})


@app.route('/api/schedule/today', methods=['GET'])
def schedule_today():
    try:
        from datetime import datetime
        tz_utc = pytz.timezone('UTC')
        today = datetime.now(tz_utc).replace(hour=0, minute=0, second=0, microsecond=0)
        schedules = db.get_schedule_for_day(today)
        # Convert datetime to ISO strings when present
        def serialize(s):
            return {
                'id': s.get('id'),
                'scheduled_at': s.get('scheduled_at').isoformat() if s.get('scheduled_at') else None,
                'executed': s.get('executed'),
                'executed_at': s.get('executed_at').isoformat() if s.get('executed_at') else None,
                'result': s.get('result')
            }
        return jsonify({'success': True, 'schedules': [serialize(s) for s in (schedules or [])]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/schedule/recompute', methods=['POST'])
def schedule_recompute():
    try:
        data = request.json or {}
        count = int(data.get('count', os.getenv('DAILY_SCHEDULES', '1')))
        from scheduler_service import AutoScheduler
        scheduler = AutoScheduler()
        schedules = scheduler._generate_daily_schedule(count)
        # Serialize
        res = []
        for s in schedules:
            res.append({
                'id': s.get('id'),
                'scheduled_at': s.get('scheduled_at').isoformat() if s.get('scheduled_at') else None,
                'executed': s.get('executed')
            })
        return jsonify({'success': True, 'schedules': res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    # Ensure static folder exists
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=False)
