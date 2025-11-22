from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
from publisher import process_and_upload
from database import db
import threading
import os
from datetime import datetime

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
content_mgr = ContentManager()
youtube_mgr = YouTubeManager()
if not generator.audio_enabled:
    print("⚠️ Audio features are disabled. Ensure pydub is installed and ffmpeg is on PATH for full audio functionality.")

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
        # Generate content using Gemini
        data = request.json or {}
        auto_upload = data.get('auto_upload', True)
        content = content_mgr.generate_content()
        
        # Process generation and optional upload through helper
        result = process_and_upload(content, generator, youtube_mgr, filename_prefix='ai', auto_upload=auto_upload)
        if not result.get('success'):
            return jsonify({"success": False, "error": result.get('error', 'Generation failed')}), 500
        video_path = result.get('video_path')

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
    return send_file(os.path.join("output", filename), as_attachment=True)

@app.route('/api/auth/youtube', methods=['POST'])
def auth_youtube():
    try:
        success = youtube_mgr.authenticate()
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    try:
        return jsonify({"authenticated": youtube_mgr.is_authenticated()})
    except Exception as e:
        return jsonify({"authenticated": False, "error": str(e)})


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

if __name__ == '__main__':
    # Ensure static folder exists
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
