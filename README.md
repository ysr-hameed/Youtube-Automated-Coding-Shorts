Environment variables to configure automation:
- `ENABLE_UPLOAD` (true/false) — Allow uploads to YouTube
- `DAILY_UPLOAD_LIMIT` (integer) — Maximum number of videos to upload per day
- `CRON_SECRET` or `CRON_TOKEN` — Optional secret to protect cron endpoint
# 🎬 Shorts Video Generator

A beautiful Python-based application to generate professional coding tutorial shorts videos with typing animations, syntax highlighting, and terminal simulations.

## ✨ Features

- **9:16 Aspect Ratio**: Perfect for YouTube Shorts, TikTok, and Instagram Reels
- **Atom One Dark Theme**: Professional, eye-pleasing color scheme
- **Character-by-Character Typing**: Realistic typing animations for questions and code
- **Syntax Highlighting**: Beautiful code presentation with keyword, string, and number highlighting
- **Line Numbers**: Professional code editor look
- **Terminal Simulation**: Animated terminal with slide-up effect and command execution
- **Modern Web UI**: Clean, professional interface to generate videos
- **High Quality Output**: MP4 videos ready for upload

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- pip
 - ffmpeg (system binary in PATH) - required for audio processing (pydub) and final audio/video merging

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Install ffmpeg (Linux / Debian/Ubuntu):
```bash
sudo apt-get update && sudo apt-get install -y ffmpeg
```

2. Run the server:
```bash
python app.py
```

3. Open your browser to:
```
http://localhost:5000
```

## 📖 Usage

### Via Web Interface

1. Open `http://localhost:5000` in your browser
2. Fill in the form:
   - **Question**: The coding question to display
   - **Code**: The code solution
   - **Command**: Terminal command to run (e.g., `node index.js`)
   - **Output**: Expected output
3. Click "Generate Video"
4. Download your video!

### Auto-upload behavior
- When using the AI generator ("✨ Generate Viral Short"), if you previously authorized YouTube, the app will automatically attempt to upload the generated video using the saved token.
- If you want to disable uploads, either revoke the stored token in the database or set the `ENABLE_UPLOAD=false` environment variable.

### Programmatically

```python
from video_generator import ShortsVideoGenerator

generator = ShortsVideoGenerator()

question = "Write a simple function to find the average number between 3 numbers"
code = """function average(a, b, c) {
  return (a + b + c) / 3;
}

console.log(average(10, 20, 30));"""
command = "node index.js"
output = "20"

generator.generate_video(question, code, command, output, "my_video")
```

## 🎨 Customization

You can customize colors and styling by modifying:

- `video_generator.py`: Video generation settings, colors, fonts, dimensions
- `static/styles.css`: Web interface styling

## 📁 Project Structure

```
Vid Generator/
├── app.py                 # Flask web server
├── video_generator.py     # Core video generation logic
├── requirements.txt       # Python dependencies
├── static/
│   ├── index.html        # Web interface
│   ├── styles.css        # Styling
│   └── script.js         # Frontend logic
├── output/               # Generated videos (created automatically)
└── frames/               # Temporary frames (created automatically)
```

## 🛠️ Technical Details

### Video Specifications

- **Resolution**: 1080x1920 (9:16)
- **Frame Rate**: 30 FPS
- **Codec**: MP4V
- **Font**: DejaVu Sans Mono (monospace)

## 🕰️ Cron / Automation

You can trigger automatic generation and upload via `GET /api/cron/generate`.
- Optional query param: `?secret=CRON_SECRET` if you have the `CRON_SECRET` set in your environment.
- Optional param: `?count=N` to generate N videos in a single run (still limited by `DAILY_UPLOAD_LIMIT`).

Scheduler and upload limits:
- Set `DAILY_UPLOAD_LIMIT` in your environment to limit how many videos will be uploaded per day.
- Set `ENABLE_UPLOAD=true` to allow the app to upload videos to YouTube. If false, videos will be generated and saved locally.
 - Set `ENABLE_UPLOAD=true` to allow the app to upload videos to YouTube. If false, videos will be generated and saved locally.

### Scheduler settings

- `DAILY_SCHEDULES`: number of randomized runs per day (default 1). Schedules are randomly assigned between 8:00 and 21:00 IST with a minimum of 30 minutes gap.
- `DAILY_SCHEDULE_TIMES`: optional, explicit comma-separated times (in IST HH:MM) to use instead of randomized scheduling. Example: `DAILY_SCHEDULE_TIMES=08:30,12:00,19:00`. If this is set, `DAILY_SCHEDULES` is ignored.
- `SCHEDULE_TIMEOUT_SECONDS`: time in seconds to wait for a scheduled run to complete (default 600). Scheduled runs that exceed the timeout are marked as failed and will not be retried automatically.
 - `DAILY_MIN_GAP_MINUTES`: minimum minutes between scheduled runs (default 60, meaning runs are at least 1 hour apart).

### Database connection tuning

- `DB_CONNECT_TIMEOUT`: maximum seconds to wait while establishing a connection to Postgres (default 10).
- `DB_RETRIES`: number of attempts to retry the connection before falling back to in-memory mock (default 3).
- `DB_RETRY_DELAY`: seconds to wait between retries (default 2).
 - `DB_VALIDATE_ON_START`: validate DB connectivity on startup (default true). If true, the app attempts to connect once to verify credentials; if unreachable, the app falls back to mock storage and logs a message.
 - `DB_VALIDATE_ON_START`: validate DB connectivity on startup (default true). If true, the app attempts to connect once to verify credentials; if unreachable, the app falls back to mock storage and logs a message.
 - `DB_CONNECT_AFTER_START`: boolean to control whether to attempt a background DB connection after the server starts (useful to let networking come up before connecting). Default true.
 - `DB_CONNECT_AFTER_START_DELAY`: seconds to delay the after-start DB connection attempt (default 10)
 - `DB_LOG_SUPPRESSION_SECONDS`: number of seconds to suppress repeated database connection error logs after the first failure. This helps keep logs readable if DB is temporarily down or has auth issues.

If DB is unavailable, the app will fall back to in-memory mock storage to keep running; however, persistence will be lost until a DB connection becomes available.

When the server starts it will ensure that today's schedule is created and persisted in the database and the UI will display scheduled times for the day.

### Animation Timeline

1. Question typing (char-by-char)
2. 2-second pause
3. Code typing (char-by-char with syntax highlighting)
4. 1-second pause
5. Terminal slide-up animation
6. Command typing
7. 1.5-second pause
8. Output display
9. 2-second hold at end

## 🎯 Tips for Best Results

- Keep questions concise and clear
- Use proper code formatting with consistent indentation
- Keep code under 40 characters per line for best display
- Use simple, readable commands
- Keep output brief for better visibility

## 🐛 Troubleshooting

**Video generation fails:**
- Ensure all dependencies are installed
- Check that fonts are available on your system
- Verify Python version is 3.8+
 - If you see audio related errors or "ImportError" for audio libraries:
   1. Ensure `ffmpeg` binary is installed and available on PATH: `which ffmpeg` should produce a path.
   2. Ensure `pydub` is installed: `pip install pydub`.
   3. If ffmpeg is installed in a non-standard location, export it for pydub or set it manually in code:

```python
from pydub import AudioSegment
from pydub.utils import which
AudioSegment.converter = which("ffmpeg") or "/usr/bin/ffmpeg"
```

You can also run a quick environment check to see if necessary binaries and packages are present:

```bash
python tools/check_audio_env.py
```

Audio customization
- Add your keyboard samples in `audio/keys/` (small .wav or .mp3 files) to enable realistic keyboard sound during typing. We will randomly pick samples for each keystroke.
 - Add your keyboard samples in `audio/keys/` (small .wav or .mp3 files) to enable realistic keyboard sound during typing. We will randomly pick samples for each keystroke. Aim for very short keypress files (30-100ms) for best results.
- Add `audio/background.mp3` (or .wav/.ogg) to include an ambient background music track at low volume across the video. If not present, the tool falls back to a synthesized ambient pad.
- Optional: Add `audio/enter.mp3` to use a realistic enter key sound instead of the synthesized one.

**Web interface not loading:**
- Make sure Flask is running
- Check port 5000 is not in use
- Verify static files exist in `static/` directory

## 📄 License

MIT License - Feel free to use and modify!

## 🙌 Credits

Built with ❤️ using:
- Python
- Pillow (PIL)
- OpenCV
- Flask
- Modern CSS & JavaScript

---

Made for creating awesome coding shorts! 🚀
