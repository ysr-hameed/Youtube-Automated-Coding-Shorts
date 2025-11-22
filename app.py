from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
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
    
    filename = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_path = generator.generate_video(question, code, filename)
    
    return jsonify({
        "success": True,
        "video_url": f"/api/download/{filename}.mp4"
    })

@app.route('/api/ai/generate', methods=['POST'])
def ai_generate():
    # Generate content using Gemini
    content = content_mgr.generate_content()
    
    filename = f"ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_path = generator.generate_video(
        content['question'],
        content['code'],
        filename
    )
    
    return jsonify({
        "success": True,
        "content": content,
        "video_url": f"/api/download/{filename}.mp4"
    })

@app.route('/api/download/<filename>')
def download(filename):
    return send_file(os.path.join("output", filename), as_attachment=True)

@app.route('/api/auth/youtube', methods=['POST'])
def auth_youtube():
    success = youtube_mgr.authenticate()
    return jsonify({"success": success})

if __name__ == '__main__':
    # Ensure static folder exists
    os.makedirs('static', exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
