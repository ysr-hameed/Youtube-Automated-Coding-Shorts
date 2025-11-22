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

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
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
