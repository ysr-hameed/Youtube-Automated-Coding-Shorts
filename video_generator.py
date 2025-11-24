import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
import shutil
import logging

# pydub is optional; not all environments have it installed or have ffmpeg on PATH
try:
    from pydub import AudioSegment
    from pydub.generators import Sine, WhiteNoise
    PYDUB_AVAILABLE = True
except Exception:
    PYDUB_AVAILABLE = False

from gtts import gTTS
import subprocess
import time
import tempfile
import re
import json
import random
import math

class CodeExecutor:
    @staticmethod
    def run_code(language, code, timeout=5):
        """Execution disabled in the generator to avoid running untrusted code.
        Always return empty output, allowing AI-provided output to be used instead."""
        return ('', 0)

class ShortsVideoGenerator:
    def __init__(self, cursor_style='_'):
        # 9:16 Shorts Resolution
        self.width = 1080
        self.height = 1920
        self.fps = 30
        
        # Define random options
        # Modern readable palettes (avoid harsh green/light blue themes)
        self.themes = {
            'dracula': {
                'bg_color': (40, 42, 54),
                'text_color': (248, 248, 242),
                'colors': {
                    'keyword': (189, 147, 249),
                    'function': (80, 250, 123),
                    'string': (255, 121, 198),
                    'number': (247, 140, 108),
                    'comment': (98, 114, 164),
                    'operator': (139, 233, 253),
                    'bracket': (248, 248, 242),
                    'error': (255, 85, 85),
                    'cursor': (98, 114, 164),
                    'builtin': (255, 184, 108)
                }
            },
            'monokai': {
                'bg_color': (39, 40, 34),
                'text_color': (248, 248, 242),
                'colors': {
                    'keyword': (249, 38, 114),
                    'function': (166, 226, 46),
                    'string': (230, 219, 116),
                    'number': (174, 129, 255),
                    'comment': (117, 113, 94),
                    'operator': (248, 248, 242),
                    'bracket': (248, 248, 242),
                    'error': (249, 38, 114),
                    'cursor': (166, 226, 46),
                    'builtin': (102, 217, 239)
                }
            },
            'solarized_dark': {
                'bg_color': (0, 43, 54),
                'text_color': (131, 148, 150),
                'colors': {
                    'keyword': (38, 139, 210),
                    'function': (42, 161, 152),
                    'string': (133, 153, 0),
                    'number': (181, 137, 0),
                    'comment': (88, 110, 117),
                    'operator': (131, 148, 150),
                    'bracket': (131, 148, 150),
                    'error': (220, 50, 47),
                    'cursor': (42, 161, 152),
                    'builtin': (211, 54, 130)
                }
            },
            'github_light': {
                'bg_color': (255, 255, 255),
                'text_color': (36, 41, 46),
                'colors': {
                    'keyword': (0, 90, 200),
                    'function': (6, 125, 70),
                    'string': (215, 56, 38),
                    'number': (153, 44, 144),
                    'comment': (115, 118, 123),
                    'operator': (36, 41, 46),
                    'bracket': (36, 41, 46),
                    'error': (200, 60, 60),
                    'cursor': (0, 90, 200),
                    'builtin': (153, 44, 144)
                }
            }
        }
        
        self.cursors = ['_', '|', '█', '▊', '▌']
        # gTTS language codes - avoid deprecated variants (e.g. 'en-in') to prevent fallback warnings
        self.tts_voices = ['en', 'en-us', 'en-gb', 'en-ca']  # gTTS langs
        self.languages = ['javascript', 'python', 'java', 'cpp', 'csharp']
        self.language_extensions = {'javascript': 'js', 'python': 'py', 'java': 'java', 'cpp': 'cpp', 'csharp': 'cs'}
        self.language_commands = {'javascript': 'node', 'python': 'python3', 'java': 'java', 'cpp': 'g++', 'csharp': 'dotnet'}
        self.video_styles = ['typing', 'fade_in', 'slide_up']  # Different animation styles
        
        # Randomly select for this instance
        self.selected_theme = random.choice(list(self.themes.keys()))
        
        # Smart color selection based on theme
        theme = self.themes[self.selected_theme]
        bg_brightness = sum(theme['bg_color']) / 3
        if bg_brightness > 128:  # Light background
            self.question_colors = [(0, 0, 0), (0, 0, 255), (0, 128, 0), (255, 0, 0), (128, 0, 128)]  # Dark colors
        else:  # Dark background
            self.question_colors = [(255, 255, 255), (255, 215, 0), (173, 216, 230), (255, 182, 193), (152, 195, 121)]  # Light colors
        
        self.selected_cursor = random.choice(self.cursors)
        self.selected_question_color = random.choice(self.question_colors)
        self.selected_tts_voice = random.choice(self.tts_voices)
        self.selected_language = random.choice(self.languages)
        self.selected_style = random.choice(self.video_styles)
        # Terminal themes (separate from code themes) to provide varied terminal looks
        self.terminal_themes = {
            'classic_dark': {
                'bg': (18, 18, 18),
                'header_bg': (30, 30, 30),
                'text': (200, 200, 200),
                'accent': (80, 200, 120),
                'cursor': (80, 200, 120),
                'success': (80, 200, 120),
                'error': (220, 85, 85)
            },
            'matrix': {
                'bg': (2, 17, 8),
                'header_bg': (5, 30, 10),
                'text': (150, 255, 150),
                'accent': (80, 255, 120),
                'cursor': (80, 255, 120),
                'success': (80, 255, 120),
                'error': (255, 80, 80)
            },
            'solarized_term': {
                'bg': (7, 54, 66),
                'header_bg': (0, 43, 54),
                'text': (131, 148, 150),
                'accent': (38, 139, 210),
                'cursor': (38, 139, 210),
                'success': (42, 161, 152),
                'error': (220, 50, 47)
            },
            'light_terminal': {
                'bg': (245, 247, 250),
                'header_bg': (230, 233, 237),
                # Use darker text on light backgrounds to ensure contrast
                'text': (20, 20, 20),
                'accent': (0, 102, 204),
                'cursor': (0, 102, 204),
                'success': (0, 120, 60),
                'error': (180, 40, 40)
            }
        }
        self.selected_terminal_theme = random.choice(list(self.terminal_themes.keys()))
        self.terminal_theme = self.terminal_themes[self.selected_terminal_theme]
        # Allow cursor per terminal theme to be randomized
        self.selected_term_cursor = random.choice(self.cursors)
        
        self.cursor_style = self.selected_cursor
        
        # Apply selected theme
        theme = self.themes[self.selected_theme]
        self.bg_color = theme['bg_color']
        self.text_color = theme['text_color']
        self.colors = theme['colors']
        
        self.mac_colors = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]
        
        # Directories
        self.output_dir = "output"
        self.audio_dir = "audio"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.audio_dir, exist_ok=True)

        # Try loading keyboard samples from audio/keys
        self.key_samples = []
        
        # Check audio capabilities
        self.ffmpeg_available = shutil.which('ffmpeg') is not None
        if not PYDUB_AVAILABLE:
            logging.info("pydub not installed. Audio features will be disabled.")
        if not self.ffmpeg_available:
            logging.info("ffmpeg not found in PATH. Audio features will be disabled.")

        self.audio_enabled = PYDUB_AVAILABLE and self.ffmpeg_available
        # Now load key samples (method exists below)
        try:
            self.key_samples = self._load_key_samples()
        except Exception:
            self.key_samples = []
        # Key samples will be loaded after initialization (below) using a method to avoid attribute errors

    def _load_key_samples(self):
        """Return a list of file paths to keyboard sound samples under audio/keys/ (mp3/wav/ogg)."""
        samples_dir = os.path.join(self.audio_dir, 'keys')
        if not os.path.exists(samples_dir):
            return []
        files = []
        for fname in os.listdir(samples_dir):
            lc = fname.lower()
            if lc.endswith('.wav') or lc.endswith('.mp3') or lc.endswith('.ogg'):
                files.append(os.path.join(samples_dir, fname))
        return files

    def _find_background_file(self):
            candidates = ['background.mp3', 'background.wav', 'background.ogg']
            for c in candidates:
                path = os.path.join(self.audio_dir, c)
                if os.path.exists(path):
                    return path
            return None

    def _find_enter_sample(self):
            candidates = ['enter.mp3', 'enter.wav', 'enter.ogg']
            for c in candidates:
                path = os.path.join(self.audio_dir, c)
                if os.path.exists(path):
                    return path
            return None

    def get_font(self, size, bold=False):
        try:
            # Try to use a good coding font if available, else default
            font_name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
            return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{font_name}", size)
        except:
            return ImageFont.load_default()

    def create_mechanical_click(self):
        """Synthesize a 'thocky' mechanical keyboard sound"""
        # If audio isn't available, just return None to indicate a disabled audio event
        if not self.audio_enabled:
            return None
        # Better mechanical 'thock' body with layered partials + short metal transient
        rand = random.Random()
        rand.seed(time.time_ns())
        # Body frequency (thock) and a harmonic; lower for deeper key feel
        # add a tiny envelope by layering two low pulses with slightly different lengths
        body_freq = rand.choice([100, 110, 125, 140, 150]) + rand.randint(-3, 3)
        body = Sine(body_freq).to_audio_segment(duration=90).apply_gain(-16 + rand.randint(-3, 1))
        body2 = Sine(int(body_freq * 2.02)).to_audio_segment(duration=110).apply_gain(-22 + rand.randint(-2, 2))
        # ping transient: high-frequency spike for the 'click' attack
        transient_freq = rand.choice([1600, 2000, 2400, 2800, 3200]) + rand.randint(-50, 50)
        # create a pair of very short transients with slight detune and a fast decay to emulate metallic bite
        transient = Sine(transient_freq).to_audio_segment(duration=12).apply_gain(-4 + rand.randint(-3, 1))
        transient2 = Sine(transient_freq + rand.choice([40, 60, 80])).to_audio_segment(duration=10).apply_gain(-8 + rand.randint(-4, 1))
        # short noise to make it more organic
        noise = WhiteNoise().to_audio_segment(duration=45).apply_gain(-30 + rand.randint(-3, 3))
        # combine with transient variations for more 'click' complexity
        sound = body.overlay(body2).overlay(transient).overlay(transient2).overlay(noise)
        # Slight fade for natural decay
        return sound.fade_in(2).fade_out(120)

    def create_random_key_click(self):
        """Synthesize a short key press sound with randomized parameters to avoid repetition."""
        if not self.audio_enabled:
            return None
        # Randomize frequency and envelope for timbral changes
        rand = random.Random()
        rand.seed(time.time_ns())
        freq = rand.choice([300, 340, 380, 420, 460, 500]) + rand.randint(-8, 8)
        dur = rand.choice([18, 22, 26, 30, 34])
        # Small two-tone body with detune
        tone = Sine(freq).to_audio_segment(duration=dur).apply_gain(-14 + rand.randint(-3, 1))
        tone2 = Sine(int(freq * 1.12)).to_audio_segment(duration=dur + 6).apply_gain(-20 + rand.randint(-3, 1))
        amber = Sine(int(freq * 0.5)).to_audio_segment(duration=int(dur*1.6)).apply_gain(-26 + rand.randint(-2, 2))
        click = WhiteNoise().to_audio_segment(duration=max(6, dur//4)).apply_gain(-26 + rand.randint(-3, 2))
        transient = Sine(rand.choice([2000, 2200, 2600, 3000])).to_audio_segment(duration=8).apply_gain(-7 + rand.randint(-2, 1))
        sound = tone.overlay(tone2).overlay(amber).overlay(click).overlay(transient)
        return sound.fade_out(10)

    def create_enter_sound(self):
        """Synthesize a heavier enter key sound"""
        if not self.audio_enabled:
            return None

        tone = Sine(300).to_audio_segment(duration=60).apply_gain(-8)
        click = WhiteNoise().to_audio_segment(duration=30).apply_gain(-16)
        sound = tone.overlay(click)
        return sound.fade_out(20)

    # legacy single-tone background function removed; we rely on the randomized
    # create_background_music below which is seeded per-call for unique tracks

    def create_background_music(self, duration_ms=10000):
        """Create a subtle looping background music segment for the full video duration.
        This uses layered low-volume sine tones and light noise for texture.
        """
        if not self.audio_enabled:
            return None

        # Randomize the base frequencies per-call so each video has a different pad
        rand = random.Random()
        # Seed with current time to get different sound each call
        rand.seed(time.time_ns())
        root = rand.choice([60, 90, 110, 130, 150, 180])
        factors = [1, 2, 3]
        freqs = [root * f for f in factors]
        # Build a layered pad/chord with low gain; small random gain shifts for variation
        base1 = Sine(freqs[0]).to_audio_segment(duration=duration_ms).apply_gain(-30 + rand.randint(-2, 2))
        base2 = Sine(freqs[1]).to_audio_segment(duration=duration_ms).apply_gain(-34 + rand.randint(-2, 2))
        base3 = Sine(freqs[2]).to_audio_segment(duration=duration_ms).apply_gain(-36 + rand.randint(-2, 2))
        # A faint noise bed
        noise = WhiteNoise().to_audio_segment(duration=duration_ms).apply_gain(-50 + rand.randint(-2, 2))
        music = base1.overlay(base2).overlay(base3).overlay(noise)
        # subtle fade in/out
        return music.fade_in(500).fade_out(500)

    def tokenize_code(self, line):
        """Tokenize a code line into [(token, type), ...] for colorized rendering.
        Returns a list of tuples where type is one of the keys in `self.colors`.
        """
        if not line:
            return []

        # Broadened token specs to handle Java, C#, Go, Python, JS common keywords and patterns
        token_specs = [
              ('builtin', r"\b(len|print|println|printf|append|push|pop|map|filter|reduce|range|make|fmt\.Println|fmt\.Printf|console\.log|System\.out\.println|toString|parseInt|parseFloat|JSON\.stringify)\b"),
              ('keyword', r"\b(function|const|let|var|return|if|else|for|while|switch|case|break|continue|try|catch|finally|throw|await|async|import|from|class|new|this|super|extends|implements|interface|package|public|private|protected|static|final|void|int|long|short|byte|char|boolean|true|false|null)\b"),
              ('string', r'(".*?"|\'.*?\')'),
              ('number', r'\b(\d+(?:\.\d+)?)\b'),
              ('comment', r'(//.*|/\*[\s\S]*?\*/|#.*)'),
              ('operator', r'([+\-*/%=<>!&|:^~]+)'),
              ('function', r'(\b\w+)(?=\()'),
              ('bracket', r'([(){}\[\];,])')
        ]

        combined = '|'.join(f"(?P<{name}>{pattern})" for name, pattern in token_specs)
        regex = re.compile(combined)

        tokens = []
        last_end = 0
        for m in regex.finditer(line):
            if m.start() > last_end:
                tokens.append((line[last_end:m.start()], 'default'))
            gname = m.lastgroup
            tokens.append((m.group(0), gname))
            last_end = m.end()
        if last_end < len(line):
            tokens.append((line[last_end:], 'default'))
        return tokens

    def wrap_line_by_width(self, draw, line, font, max_width):
        """Wrap a single line of text into multiple lines so that each fits within max_width (pixels).
        Returns a list of wrapped lines.
        """
        if not line:
            return [""]

        words = line.split(' ')
        lines = []
        current = ''
        for w in words:
            candidate = w if current == '' else f"{current} {w}"
            if draw.textlength(candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                # if single word too long for the width, split by character approx
                if draw.textlength(w, font=font) <= max_width:
                    current = w
                else:
                    part = ''
                    for ch in w:
                        if draw.textlength(part + ch, font=font) <= max_width:
                            part += ch
                        else:
                            if part:
                                lines.append(part)
                            part = ch
                    if part:
                        current = part
                    else:
                        current = ''
        if current != '':
            lines.append(current)
        return lines

    def generate_video(self, question, code, filename="viral_short", output_text=None, language=None):
        # Allow passing an explicit language per video; otherwise pick a random one per-call
        if language and language in self.languages:
            self.selected_language = language
        else:
            # randomize per call to avoid repeated Python-only output
            self.selected_language = random.choice(self.languages)
        print(f"🚀 Generating Viral Short: {filename} (lang={self.selected_language})")
        
        # 1. Use AI-provided code as the "result" instead of executing it locally.
        # This avoids requiring language runtimes and prevents execution errors.
        print("⚙️ Using AI-provided code as output (execution disabled)")
        # Use the AI-provided output_text (preferred) otherwise fall back to code as display
        real_output = (output_text.strip() if output_text else (code.strip() if code else ""))
        return_code = 0

        # 2. Audio Setup (TTS)
        # Generate TTS only when audio generation is enabled
        tts_path = None
        # Deterministic fallback duration per character (ms) when TTS audio not available.
        try:
            base_ms_per_char = float(os.getenv('BASE_MS_PER_CHAR', '55'))
        except Exception:
            base_ms_per_char = 55.0
        tts_duration_ms = max(300, int(len(question) * base_ms_per_char))  # approximate fallback (ms)
        if self.audio_enabled:
            try:
                print("🗣️ Generating TTS...")
                tts = gTTS(text=question, lang=self.selected_tts_voice, slow=False)
                tts_path = os.path.join(self.audio_dir, "tts.mp3")
                tts.save(tts_path)
                tts_audio = AudioSegment.from_mp3(tts_path)
                tts_duration_ms = len(tts_audio)
            except Exception as e:
                logging.warning(f"TTS or audio load failed, continuing without audio: {e}")
                tts_path = None
                # keep deterministic fallback duration (scaled by speedup later)
        
        # Calculate typing speed to match TTS
        # We want the question typing to finish exactly when TTS finishes.
        # Use a single SPEEDUP_FACTOR env var to speed both speech and typing together.
        total_chars_question = len(question)
        try:
            speedup = float(os.getenv('SPEEDUP_FACTOR', '1.0'))
            if speedup <= 0:
                speedup = 1.0
        except Exception:
            speedup = 1.0

        # If pydub is available, we can physically speed up the TTS audio so playback is faster.
        if self.audio_enabled and tts_path and speedup != 1.0:
            try:
                from pydub import effects
                tts_audio = effects.speedup(tts_audio, playback_speed=speedup)
                # overwrite the tts file with the sped-up version
                tts_audio.export(tts_path, format='mp3')
                tts_duration_ms = len(tts_audio)
            except Exception:
                # Fallback: adjust perceived duration numerically
                try:
                    tts_duration_ms = int(tts_duration_ms / speedup)
                except Exception:
                    pass

        # If audio isn't enabled or tts_path wasn't produced, scale fallback duration by speedup
        if (not self.audio_enabled) or (tts_path is None):
            try:
                tts_duration_ms = int(tts_duration_ms / speedup)
            except Exception:
                pass

        # Compute ms per character so typing finishes when TTS finishes
        ms_per_char_question = (tts_duration_ms / max(1, total_chars_question))
        if self.selected_style == 'fade_in':
            ms_per_char_question *= 2  # Slower typing for fade effect
        frames_per_char_question = max(1, int((ms_per_char_question / 1000) * self.fps))

        # Stream frames directly to disk to avoid keeping all frames in memory
        temp_video = os.path.join(self.output_dir, "temp_vid.mp4")
        out = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'mp4v'), self.fps, (self.width, self.height))
        frame_count = 0
        last_frame_img = None

        def append_frame(img, repeats=1):
            nonlocal frame_count, last_frame_img
            bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            for _ in range(repeats):
                out.write(bgr)
                frame_count += 1
            last_frame_img = img
        
        # --- VISUAL CONFIG ---
        # Huge Fonts
        font_code = self.get_font(48) 
        font_question = self.get_font(55, bold=True)
        font_header = self.get_font(40)
        font_terminal = self.get_font(42)
        
        margin_x = 80
        header_y = 100
        question_y = 200
        code_y = 380 # Start code lower to give space for question
        # Width reserved for line numbers (pixels). Increase for extra space to the right of numbers.
        try:
            line_number_area_width = int(os.getenv('LINE_NUMBER_AREA_WIDTH', '120'))
        except Exception:
            line_number_area_width = 120
        code_x = margin_x + line_number_area_width
        try:
            right_padding = int(os.getenv('RIGHT_PADDING', '60'))
        except Exception:
            right_padding = 60
        
        # --- PHASE 1: HEADER & BACKGROUND ---
        def create_bg():
            img = Image.new('RGB', (self.width, self.height), self.bg_color)
            draw = ImageDraw.Draw(img)
            
            # Mac Dots (Huge)
            dot_size = 40
            dot_spacing = 80
            start_x = margin_x
            for i, color in enumerate(self.mac_colors):
                x = start_x + (i * dot_spacing)
                draw.ellipse([x, header_y, x + dot_size, header_y + dot_size], fill=color)
            
            # Filename
            draw.text((self.width//2 - 100, header_y - 5), f"index.{self.language_extensions[self.selected_language]}", font=font_header, fill=self.colors['comment'])
            return img, draw

        # --- PHASE 2: QUESTION TYPING (Synced with TTS) ---
        wrapped_question = textwrap.wrap(question, width=25) # Narrow width for huge text
        
        current_q_text = ""
        q_char_count = 0
        
        audio_events = []
        if tts_path:
            audio_events.append((0, 'tts', tts_path))
        # Throttle key audio events so short samples don't create a rapid-fire impression.
        try:
            key_min_interval_ms = int(os.getenv('KEY_MIN_INTERVAL_MS', '60'))
        except Exception:
            key_min_interval_ms = 60
        last_key_event_ms = -999999
        
        # Flatten wrapped lines for typing calculation
        flat_question = "\n".join(wrapped_question)
        
        # We'll compute a dynamic code start Y after we know the question height
        # Create a temporary draw context to measure text height
        img_tmp, draw_tmp = create_bg()
        q_line_h = draw_tmp.textbbox((0,0), "Ay", font=font_question)[3] - draw_tmp.textbbox((0,0), "Ay", font=font_question)[1]
        question_height_px = q_line_h * max(1, len(wrapped_question)) + 20
        # Allow configurable gap between the question block and the code block
        try:
            question_code_gap = int(os.getenv('QUESTION_CODE_GAP', '60'))
        except Exception:
            question_code_gap = 60
        code_y = question_y + question_height_px + question_code_gap

        slide_offset = 50 if self.selected_style == 'slide_up' else 0
        char_count = 0

        # Distribute frames per character so typing finishes exactly when TTS audio finishes.
        total_chars = len(flat_question)
        total_frames_available = max(1, int((tts_duration_ms / 1000.0) * self.fps))
        base_frames = total_frames_available // max(1, total_chars)
        remainder = total_frames_available - (base_frames * max(1, total_chars))
        frames_per_char_list = [base_frames + (1 if i < remainder else 0) for i in range(total_chars)]

        for idx, char in enumerate(flat_question):
            img, draw = create_bg()

            # Draw typed question so far
            current_q_text += char
            char_count += 1

            # Update slide for slide_up style
            if self.selected_style == 'slide_up':
                slide_offset = max(0, 50 - (char_count * 1))  # Slide up 1 pixel per char

            # Re-wrap the current text to draw it correctly line by line
            curr_lines = current_q_text.split('\n')

            y = question_y + slide_offset
            for line in curr_lines:
                draw.text((margin_x, y), line, font=font_question, fill=self.selected_question_color)
                y += 80

            # Cursor (use terminal-neutral cursor style for question area)
            cursor_pos = draw.textlength(curr_lines[-1], font=font_question)
            draw.text((margin_x + cursor_pos, y - 80), self.selected_cursor, font=font_question, fill=self.colors['cursor'])

            # Add frames (streamed) - distributed per character
            repeats = frames_per_char_list[idx] if idx < len(frames_per_char_list) else base_frames
            repeats = max(1, repeats)
            append_frame(img, repeats)

            # Key sound events: append 'key' event (sample index) or fall back to click
            if char.strip() and self.audio_enabled:
                time_ms = int((frame_count / self.fps) * 1000)
                if time_ms - last_key_event_ms >= key_min_interval_ms:
                    if self.key_samples:
                        sample_idx = random.randrange(0, len(self.key_samples))
                        audio_events.append((time_ms, 'key', sample_idx))
                    else:
                        audio_events.append((time_ms, 'key', None))
                    last_key_event_ms = time_ms

        # Hold after question (repeat last written frame)
        if last_frame_img is not None:
            append_frame(last_frame_img, 15)

        # --- PHASE 3: CODE TYPING ---
        code_lines = code.split('\n')
        # Build wrapped code lines to prevent visual overflow in the video
        img_tmp, draw_tmp = create_bg()
        max_code_width_px = self.width - margin_x - 60 - margin_x

        def wrap_code_line(draw, text, font, max_px):
            # Preserve indentation
            leading_ws = re.match(r"^(\s*)", text).group(1)
            stripped = text[len(leading_ws):]
            if not stripped:
                return [leading_ws]

            tokens = re.split(r"(\s+)", stripped)
            lines = []
            curr = leading_ws
            for token in tokens:
                # If token alone is too large, break it into characters
                if draw.textlength(curr + token, font=font) <= max_px:
                    curr += token
                else:
                    if curr.strip() or curr != leading_ws:
                        lines.append(curr)
                    # If token itself is too long, break by character
                    if draw.textlength(leading_ws + token, font=font) > max_px:
                        piece = ''
                        for ch in token:
                            if draw.textlength(leading_ws + piece + ch, font=font) <= max_px:
                                piece += ch
                            else:
                                lines.append(leading_ws + piece)
                                piece = ch
                        if piece:
                            curr = leading_ws + piece
                        else:
                            curr = leading_ws
                    else:
                        curr = leading_ws + token.lstrip()
            if curr.strip() or curr != leading_ws:
                lines.append(curr)
            return lines

        wrapped_code_lines = []
        for l in code_lines:
            sub = wrap_code_line(draw_tmp, l, font_code, max_code_width_px)
            wrapped_code_lines.extend(sub)
        current_code_lines = []
        
        # Faster typing for code (user adjustable). Base frames per char can be tuned with FRAMES_PER_CHAR_CODE
        try:
            base_frames_per_char_code = int(os.getenv('FRAMES_PER_CHAR_CODE', '1'))
        except Exception:
            base_frames_per_char_code = 2
        # Scale code typing speed with SPEEDUP_FACTOR (higher -> fewer frames per char) and allow a code-specific speed factor
        try:
            code_speed_factor = float(os.getenv('CODE_SPEED_FACTOR', '1.0'))
        except Exception:
            code_speed_factor = 1.0
        try:
            frames_per_char_code = max(1, int(base_frames_per_char_code / max(0.01, (speedup * code_speed_factor))))
        except Exception:
            frames_per_char_code = max(1, int(base_frames_per_char_code))
        
        for line_idx, line in enumerate(wrapped_code_lines):
            current_code_lines.append("")
            
            # Indentation
            indent = len(line) - len(line.lstrip())
            current_code_lines[-1] = " " * indent
            
            for char in line[len(" " * indent):]:
                img, draw = create_bg()
                
                # Draw Question (Static)
                y = question_y
                for q_line in wrapped_question:
                    draw.text((margin_x, y), q_line, font=font_question, fill=self.selected_question_color)
                    y += 80
                
                # Draw Code
                current_code_lines[-1] += char
                
                cy = code_y
                for idx, c_line in enumerate(current_code_lines):
                    wrapped_sub = wrap_code_line(draw, c_line, font_code, max_code_width_px)
                    # Simple syntax highlighting (Keyword detection for whole words)
                    # For char-by-char, we just draw the whole line for now to keep it stable
                    # A full lexer for partial lines is complex, so we'll colorize fully typed words
                    # and keep current word white
                    
                    # Draw line number
                    # draw.text((margin_x, cy), "1", font=font_code, fill=self.colors['comment'])
                    
                    # Draw code text (handle wrapped lines)
                    for wi, sub in enumerate(wrapped_sub):
                        # Draw line number only for the first wrapped subline
                        if wi == 0:
                            line_num = str(idx + 1)
                            draw.text((margin_x, cy), line_num, font=font_code, fill=self.colors['comment'])
                        # Colorize via tokens
                        tokens = self.tokenize_code(sub)
                        x = code_x
                        for token, typ in tokens:
                            color = self.colors.get(typ, self.text_color)
                            draw.text((x, cy), token, font=font_code, fill=color)
                            x += draw.textlength(token, font=font_code)
                        cy += 70
                
                # Cursor
                # Compute cursor position considering wrapping of the last line
                last_wrapped = wrap_code_line(draw, current_code_lines[-1], font_code, max_code_width_px)
                last_line_width = draw.textlength(last_wrapped[-1], font=font_code) if last_wrapped else 0
                draw.text((code_x + last_line_width, cy - 70), self.cursor_style, font=font_code, fill=self.colors['cursor'])
                
                append_frame(img, frames_per_char_code)
                
                # Key sound events for code typing
                if char.strip() and self.audio_enabled:
                    time_ms = int((frame_count / self.fps) * 1000)
                    if time_ms - last_key_event_ms >= key_min_interval_ms:
                        if self.key_samples:
                            sample_idx = random.randrange(0, len(self.key_samples))
                            audio_events.append((time_ms, 'key', sample_idx))
                        else:
                            audio_events.append((time_ms, 'key', None))
                        last_key_event_ms = time_ms
            
            # Newline pause - repeat the last written frame a few times
            if last_frame_img is not None:
                append_frame(last_frame_img, 5)

    # No enter/keyboard sounds: omit enter sound
        
        # --- PHASE 4: TERMINAL EXECUTION ---
        # --- PHASE 4: TERMINAL EXECUTION ---
        # Terminal slide animation: randomly choose an entry direction: up, left, right
        try:
            term_height = int(os.getenv('TERM_HEIGHT_PX', '600'))
        except Exception:
            term_height = 600
        # Allow a global bottom offset so terminal doesn't touch very bottom of video
        try:
            term_global_bottom_offset = int(os.getenv('TERM_GLOBAL_BOTTOM_OFFSET_PX', '12'))
        except Exception:
            term_global_bottom_offset = 12
        # Terminal padding from each side (overrides/augments inner padding)
        try:
            term_pad_left = int(os.getenv('TERM_PAD_LEFT_PX', '12'))
        except Exception:
            term_pad_left = 12
        try:
            term_pad_right = int(os.getenv('TERM_PAD_RIGHT_PX', '12'))
        except Exception:
            term_pad_right = 12
        try:
            term_pad_top = int(os.getenv('TERM_PAD_TOP_PX', '12'))
        except Exception:
            term_pad_top = 12
        try:
            term_pad_bottom = int(os.getenv('TERM_PAD_BOTTOM_PX', '24'))
        except Exception:
            term_pad_bottom = 24


        term_y_end = self.height - term_height - term_global_bottom_offset
        # Random slide direction (up, left, right)
        directions = ['up', 'left', 'right']
        term_direction = random.choice(directions)

        # Terminal theme colors
        t_bg = self.terminal_theme.get('bg', (20, 20, 20))
        t_header_bg = self.terminal_theme.get('header_bg', (40, 40, 40))
        t_text = self.terminal_theme.get('text', (220, 220, 220))
        t_accent = self.terminal_theme.get('accent', (80, 200, 120))
        t_cursor_color = self.terminal_theme.get('cursor', t_accent)
        # Inner padding inside the terminal box (small, to avoid large left gaps)
        term_inner_pad = int(os.getenv('TERM_INNER_PADDING_PX', '12'))
        # Right padding inside terminal to keep text away from edge
        term_inner_right = int(os.getenv('TERM_INNER_RIGHT_PX', '12'))
        # Bottom padding inside terminal so logs don't touch the bottom edge
        term_bottom_pad = int(os.getenv('TERM_BOTTOM_PADDING_PX', '24'))
        # Header height for terminal (pixels)
        term_header_h = int(os.getenv('TERM_HEADER_HEIGHT_PX', '60'))

        # Final terminal X (anchored to left when slide finishes). If you change slide logic
        # to place the terminal elsewhere, update this accordingly.
        final_term_x = 0

        def terminal_wrap(draw, text, font, max_px):
            """Wrap `text` into a list of lines that fit within max_px using draw.textlength measurements."""
            if not text:
                return [""]
            words = text.split(' ')
            lines = []
            current = words[0]
            for w in words[1:]:
                candidate = current + ' ' + w
                if draw.textlength(candidate, font=font) <= max_px:
                    current = candidate
                else:
                    lines.append(current)
                    current = w
            if current:
                lines.append(current)
            # As a safety, if any line still exceeds max_px, break by characters
            final_lines = []
            for ln in lines:
                if draw.textlength(ln, font=font) <= max_px:
                    final_lines.append(ln)
                else:
                    part = ''
                    for ch in ln:
                        if draw.textlength(part + ch, font=font) <= max_px:
                            part += ch
                        else:
                            final_lines.append(part)
                            part = ch
                    if part:
                        final_lines.append(part)
            return final_lines

        # Slide duration (seconds) -> frames. Default to 0.5s for a snappy slide.
        try:
            term_slide_duration = float(os.getenv('TERM_SLIDE_DURATION_SEC', '0.5'))
            term_slide_frames = max(1, int(term_slide_duration * self.fps))
        except Exception:
            term_slide_frames = max(1, int(0.5 * self.fps))

        for i in range(term_slide_frames):
            img, draw = create_bg()
            # Draw static content above the terminal
            y = question_y
            for q_line in wrapped_question:
                draw.text((margin_x, y), q_line, font=font_question, fill=self.selected_question_color)
                y += 80
            cy = code_y
            for idx, c_line in enumerate(current_code_lines):
                wrapped_sub = wrap_code_line(draw, c_line, font_code, max_code_width_px)
                for wi, sub in enumerate(wrapped_sub):
                    if wi == 0:
                        line_num = str(idx + 1)
                        draw.text((margin_x, cy), line_num, font=font_code, fill=self.colors['comment'])
                    tokens = self.tokenize_code(sub)
                    x = code_x
                    for token, typ in tokens:
                        color = self.colors.get(typ, self.text_color)
                        draw.text((x, cy), token, font=font_code, fill=color)
                        x += draw.textlength(token, font=font_code)
                    cy += 70

            # Slide progress (0 -> 1)
            progress = i / (term_slide_frames - 1) if term_slide_frames > 1 else 1.0

            # Draw terminal sliding from chosen direction, but do NOT render header text yet.
            if term_direction == 'up':
                curr_term_y = int(self.height + (term_y_end - self.height) * progress)
                draw.rectangle([0, curr_term_y, self.width, curr_term_y + term_height], fill=t_bg)
                draw.rectangle([0, curr_term_y, self.width, curr_term_y + term_header_h], fill=t_header_bg)
            elif term_direction == 'left':
                curr_term_x = int(-self.width + (self.width * progress))
                draw.rectangle([curr_term_x, term_y_end, curr_term_x + self.width, term_y_end + term_height], fill=t_bg)
                draw.rectangle([curr_term_x, term_y_end, curr_term_x + self.width, term_y_end + term_header_h], fill=t_header_bg)
            else:  # right
                curr_term_x = int(self.width - (self.width * progress))
                draw.rectangle([curr_term_x, term_y_end, curr_term_x + self.width, term_y_end + term_height], fill=t_bg)
                draw.rectangle([curr_term_x, term_y_end, curr_term_x + self.width, term_y_end + term_header_h], fill=t_header_bg)

            append_frame(img, 1)

        # After slide completes, render the terminal at its final location with header text and use that as base image
        img, draw = create_bg()
        # Terminal final position
        draw.rectangle([0, term_y_end, self.width, term_y_end + term_height], fill=t_bg)
        draw.rectangle([0, term_y_end, self.width, term_y_end + term_header_h], fill=t_header_bg)
        # Header text now visible after slide
        draw.text((term_pad_left, term_y_end + 10), "Terminal", font=font_header, fill=t_text)
        base_term_img = img

        # Waiting State (Blinking Cursor + $) - use terminal colors and cursor shape
        # base_term_img already contains the terminal drawn at final position with header
        prompt_y = term_y_end + term_header_h + term_pad_top
        prompt_x = final_term_x + term_pad_left

        for _ in range(45): # Wait 1.5s
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)

            # Blink cursor using terminal cursor char and color; use inner terminal padding
            if _ % 8 < 4:
                draw.text((prompt_x, prompt_y), "$ " + self.selected_term_cursor, font=font_terminal, fill=t_text)
            else:
                draw.text((prompt_x, prompt_y), "$ ", font=font_terminal, fill=t_text)

            # Optional debug overlay to render terminal coordinates and padding info
            try:
                if os.getenv('TERM_DEBUG', '0') == '1':
                    debug_text = f"term_y_end={term_y_end} term_h={term_height} header_h={term_header_h} pad_top={term_pad_top} pad_left={term_pad_left} pad_right={term_pad_right}"
                    draw.text((10, 10), debug_text, font=font_header, fill=(255,255,255))
            except Exception:
                pass
            append_frame(img, 1)

        # Type Command
        command = f"{self.language_commands[self.selected_language]} index.{self.language_extensions[self.selected_language]}"
        curr_cmd = "$ "
        for char in command:
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)
            curr_cmd += char
            # Use terminal theme colors and cursor shape for prompt
            prompt_display = curr_cmd + self.selected_term_cursor
            draw.text((prompt_x, prompt_y), prompt_display, font=font_terminal, fill=t_text)
            # Make terminal typing faster by default; allow tuning
            try:
                key_frames = int(os.getenv('TERM_TYPING_FRAMES_PER_CHAR', '1'))
            except Exception:
                key_frames = 1
            append_frame(img, max(1, key_frames))

            # Key sound for terminal typing
            if char.strip() and self.audio_enabled:
                time_ms = int((frame_count / self.fps) * 1000)
                if time_ms - last_key_event_ms >= key_min_interval_ms:
                    if self.key_samples:
                        sample_idx = random.randrange(0, len(self.key_samples))
                        audio_events.append((time_ms, 'key', sample_idx))
                    else:
                        audio_events.append((time_ms, 'key', None))
                    last_key_event_ms = time_ms

        # Enter sound after command
        if self.audio_enabled:
            time_ms = int((frame_count / self.fps) * 1000)
            audio_events.append((time_ms, 'enter', None))
    # No enter sound (keyboard noises disabled)

        # Show Result
        output_lines = real_output.split('\n')
        result_color = self.colors['error'] if return_code != 0 else self.colors['string']
        
        # Hold result for 3 seconds
        for _ in range(90):
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)
            # Use terminal inner padding and terminal text color for command
            draw.text((prompt_x, prompt_y), curr_cmd, font=font_terminal, fill=t_text)

            res_y = prompt_y + 60
            # Max width available for terminal text content (respect left/right padding only)
            max_terminal_text_px = max(10, self.width - term_pad_left - term_pad_right)
            # Enforce bottom padding so logs don't run into the bottom edge of terminal
            max_res_y = term_y_end + term_height - term_bottom_pad
            for line in output_lines:
                wrapped = terminal_wrap(draw, line, font_terminal, max_terminal_text_px)
                for wline in wrapped:
                    # Colorize output using terminal error/success colors when possible
                    if return_code != 0:
                        out_color = self.terminal_theme.get('error', result_color)
                    else:
                        out_color = self.terminal_theme.get('success', result_color)
                    # If the next line would be below the allowed terminal content area, stop drawing more lines
                    if res_y + 40 > max_res_y:
                        # indicate truncation with ellipsis on the last allowed line
                        try:
                            ell = '...'
                            draw.text((prompt_x, res_y), ell, font=font_terminal, fill=out_color)
                        except Exception:
                            pass
                        res_y = max_res_y + 1
                        break
                    draw.text((prompt_x, res_y), wline, font=font_terminal, fill=out_color)
                    res_y += 50

            append_frame(img, 1)

        # --- RENDER VIDEO ---
        # All frames have been written progressively to temp_video
        print(f"🎥 Rendering complete ({frame_count} frames written) -> {temp_video}")
        out.release()

        # --- MIX AUDIO ---
        print("🎵 Mixing Audio...")
        total_duration = frame_count / self.fps * 1000
        if self.audio_enabled:
            final_audio = AudioSegment.silent(duration=total_duration)
            bg_file = self._find_background_file() if hasattr(self, '_find_background_file') else None
            # decide where background should start: after TTS if present, else at 0
            try:
                bg_start_ms = int(tts_duration_ms) if tts_path else 0
            except Exception:
                bg_start_ms = 0

            if bg_file and os.path.exists(bg_file):
                try:
                    bg = AudioSegment.from_file(bg_file)
                    # Loop background if it's shorter than remaining duration after start
                    remaining = int(total_duration) - bg_start_ms
                    if remaining <= 0:
                        # nothing to add
                        bg = None
                    else:
                        if len(bg) < remaining:
                            times = (int(remaining) // len(bg)) + 1
                            bg = bg * times
                        bg = bg[:int(remaining)]
                        # Apply default background gain and overlay at bg_start_ms
                        bg = bg.apply_gain(int(os.getenv('BG_MUSIC_GAIN_DB', '-12')))
                        final_audio = final_audio.overlay(bg, position=bg_start_ms)
                except Exception as e:
                    logging.warning(f"Failed to load custom background {bg_file}: {e}")
                    # Fallback to synthesized music
                    bg_music = self.create_background_music(max(0, int(total_duration - bg_start_ms)))
                    if bg_music is not None:
                        bg_music = bg_music.apply_gain(int(os.getenv('BG_MUSIC_GAIN_DB', '-12')))
                        final_audio = final_audio.overlay(bg_music, position=bg_start_ms)
            else:
                bg_music = self.create_background_music(max(0, int(total_duration - bg_start_ms)))
                if bg_music is not None:
                    bg_music = bg_music.apply_gain(int(os.getenv('BG_MUSIC_GAIN_DB', '-12')))
                    final_audio = final_audio.overlay(bg_music, position=bg_start_ms)
        else:
            final_audio = None
        
        click_sound = self.create_mechanical_click()
        # Make clicks a bit softer or louder based on env setting so background music sits under them; keep mechanical clicks as preferred fallback
        try:
            click_gain_db = int(os.getenv('KEY_CLICK_GAIN_DB', '-3'))
        except Exception:
            click_gain_db = -3
        if click_sound is not None:
            click_sound = click_sound.apply_gain(click_gain_db)
        # Prefer an enter sample file if present, otherwise use synthesized enter sound
        enter_sample = None
        enter_file = self._find_enter_sample() if hasattr(self, '_find_enter_sample') else None
        if enter_file and self.audio_enabled:
            try:
                enter_sample = AudioSegment.from_file(enter_file)
            except Exception:
                enter_sample = None
        enter_sound = enter_sample if enter_sample is not None else self.create_enter_sound()
        
    # If audio is not enabled, skip mixing entirely
        if self.audio_enabled:
            # Prepare background file (prefer user-provided file, otherwise keep already added bg_music)
            bg_file = self._find_background_file() if hasattr(self, '_find_background_file') else None
            if bg_file and os.path.exists(bg_file):
                try:
                    bg = AudioSegment.from_file(bg_file)
                    # Reduce background track volume substantially
                    bg = bg.apply_gain(-18)
                    final_audio = final_audio.overlay(bg)
                except Exception as e:
                    logging.warning(f"Failed to load custom background {bg_file}: {e}")

            for time_ms, type, data in audio_events:
                try:
                    if type == 'tts' and data:
                        # Increase TTS volume a bit so it sits above background/keys
                        sound = AudioSegment.from_mp3(data).apply_gain(+6)
                    elif type == 'click':
                        sound = click_sound
                    elif type == 'enter':
                        sound = enter_sound
                    elif type == 'key':
                        # data is index into self.key_samples
                        if self.key_samples and isinstance(data, int) and data < len(self.key_samples):
                            sample_path = self.key_samples[data]
                            try:
                                sound = AudioSegment.from_file(sample_path)
                                # Apply configurable gain to key samples and a small random jitter so repeated keys don't sound identical
                                try:
                                    base_gain = int(os.getenv('KEY_SAMPLE_GAIN_DB', '-3'))
                                except Exception:
                                    base_gain = -6
                                jitter = random.randint(-2, 2)
                                sound = sound.apply_gain(base_gain + jitter)
                                try:
                                    from pydub import effects
                                    # Allow configurable % variation for key sample speed. Default 0% (no change).
                                    try:
                                        var_pct = float(os.getenv('KEY_SAMPLE_SPEED_VARIATION_PERCENT', '0.0'))
                                    except Exception:
                                        var_pct = 0.0
                                    variation = max(0.0, var_pct / 100.0)
                                    if variation > 0.0:
                                        # random variation in range [-variation, +variation]
                                        speed = 1.0 + (random.random() - 0.5) * (variation * 2)
                                        # small speed adjustments; wrap in try because effects.speedup may fail in some environments
                                        sound = effects.speedup(sound, playback_speed=speed)
                                except Exception:
                                    pass
                            except Exception as e:
                                logging.warning(f"Failed to load key sample {sample_path}: {e}")
                                sound = None
                        else:
                            # Prefer a mechanical click fallback the majority of the time but add variety
                            if click_sound and random.random() < 0.8:
                                sound = click_sound
                            else:
                                sound = self.create_random_key_click() or click_sound
                    else:
                        continue
                except Exception as e:
                    logging.warning(f"Audio event failed: {e}")
                    continue

                if sound is not None:
                    final_audio = final_audio.overlay(sound, position=time_ms)
            
        temp_audio = None
        if self.audio_enabled:
            temp_audio = os.path.join(self.audio_dir, "temp_audio.mp3")
            try:
                final_audio.export(temp_audio, format="mp3")
            except Exception as e:
                logging.warning(f"Failed to export final audio: {e}")
                temp_audio = None
        
        # --- MERGE ---
        final_output = os.path.join(self.output_dir, f"{filename}.mp4")
        if self.ffmpeg_available and temp_audio:
            try:
                subprocess.run([
                    'ffmpeg', '-y', '-i', temp_video, '-i', temp_audio,
                    '-c:v', 'copy', '-c:a', 'aac', final_output
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            except Exception as e:
                logging.warning(f"ffmpeg merge failed, saving video without audio: {e}")
                # If ffmpeg merge fails, copy temp_video to final output (fallback)
                try:
                    if os.path.exists(temp_video):
                        import shutil
                        shutil.copyfile(temp_video, final_output)
                    else:
                        raise FileNotFoundError(f"temp_video not found: {temp_video}")
                except Exception as e2:
                    logging.error(f"Failed to save video without audio: {e2}")
                    raise
        else:
            # If no ffmpeg or audio, just copy the video file as final output
            try:
                if os.path.exists(temp_video):
                    import shutil
                    shutil.copyfile(temp_video, final_output)
                else:
                    raise FileNotFoundError(f"temp_video not found: {temp_video}")
            except Exception as e:
                logging.error(f"Failed to save video file without merge: {e}")
                raise
        
        # Cleanup
        # Cleanup remaining temp files if they exist
        try:
            if os.path.exists(temp_video):
                os.remove(temp_video)
        except Exception:
            pass
        try:
            if temp_audio and os.path.exists(temp_audio):
                os.remove(temp_audio)
        except Exception:
            pass
        
        return final_output

if __name__ == "__main__":
    gen = ShortsVideoGenerator()
    gen.generate_video(
        "Write a function to check if a number is even",
        "function isEven(n) {\n  return n % 2 === 0;\n}\n\nconsole.log(isEven(4));"
    )
