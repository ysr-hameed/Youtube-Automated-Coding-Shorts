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
    def run_node(code):
        """Run Node.js code and return real output or error"""
        with tempfile.NamedTemporaryFile(suffix='.js', mode='w', delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run node with a timeout
            result = subprocess.run(
                ['node', temp_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout if result.stdout else result.stderr
            return output.strip(), result.returncode
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out (5s limit)", 1
        except Exception as e:
            return f"Error: {str(e)}", 1
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

class ShortsVideoGenerator:
    def __init__(self, cursor_style='_'):
        # 9:16 Shorts Resolution
        self.width = 1080
        self.height = 1920
        self.fps = 30
        
        self.cursor_style = cursor_style
        
        # Theme - Single Unified Background (No separate editor box)
        self.bg_color = (30, 34, 40)  # Deep One Dark
        self.text_color = (220, 223, 228)
        
        # Syntax Colors (Vibrant)
        self.colors = {
            'keyword': (198, 120, 221),   # Purple
            'function': (97, 175, 239),   # Blue
            'string': (152, 195, 121),    # Green
            'number': (209, 154, 102),    # Orange
            'comment': (120, 120, 120),   # Grey
            'operator': (86, 182, 194),   # Cyan
            'bracket': (220, 223, 228),   # White
            'error': (224, 108, 117),     # Red
            'cursor': (82, 139, 255)      # Bright Blue
        }
        
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

        token_specs = [
            ('keyword', r'\b(function|const|let|var|return|if|else|for|while|console|log|await|async|import|from)\b'),
            ('string', r'(".*?"|\'.*?\')'),
            ('number', r'\b(\d+)\b'),
            ('comment', r'(//.*)'),
            ('operator', r'([+\-*/%=<>!&|]+)'),
            ('function', r'(\w+)(?=\()'),
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

    def generate_video(self, question, code, filename="viral_short"):
        print(f"🚀 Generating Viral Short: {filename}")
        
        # 1. Execute Code to get Real Output
        print("⚙️ Executing code...")
        real_output, return_code = CodeExecutor.run_node(code)
        print(f"📝 Output: {real_output}")

        # 2. Audio Setup (TTS)
        # Generate TTS only when audio generation is enabled
        tts_path = None
        tts_duration_ms = max(1000, len(question) * 55) # approximate fallback (ms)
        if self.audio_enabled:
            try:
                print("🗣️ Generating TTS...")
                tts = gTTS(text=question, lang='en', slow=False)
                tts_path = os.path.join(self.audio_dir, "tts.mp3")
                tts.save(tts_path)
                tts_audio = AudioSegment.from_mp3(tts_path)
                tts_duration_ms = len(tts_audio)
            except Exception as e:
                logging.warning(f"TTS or audio load failed, continuing without audio: {e}")
                tts_path = None
        
        # Calculate typing speed to match TTS
        # We want the question typing to finish exactly when TTS finishes
        # Allow a user-adjustable typing speed multiplier via env var TYPING_SPEED_FACTOR
        total_chars_question = len(question)
        try:
            typing_speed_factor = float(os.getenv('TYPING_SPEED_FACTOR', '1.0'))
        except Exception:
            typing_speed_factor = 1.0
        ms_per_char_question = (tts_duration_ms / max(1, total_chars_question)) * typing_speed_factor
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
            draw.text((self.width//2 - 100, header_y - 5), "index.js", font=font_header, fill=self.colors['comment'])
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
        code_y = question_y + question_height_px + 60

        for char in flat_question:
            img, draw = create_bg()

            # Draw typed question so far
            current_q_text += char

            # We need to re-wrap the current text to draw it correctly line by line
            # This is a bit inefficient but ensures correct wrapping animation
            curr_lines = current_q_text.split('\n')

            y = question_y
            for line in curr_lines:
                draw.text((margin_x, y), line, font=font_question, fill=self.colors['keyword']) # Purple question
                y += 80

            # Cursor
            cursor_pos = draw.textlength(curr_lines[-1], font=font_question)
            draw.text((margin_x + cursor_pos, y - 80), self.cursor_style, font=font_question, fill=self.colors['cursor'])

            # Add frames (streamed)
            append_frame(img, frames_per_char_question)

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
            base_frames_per_char_code = int(os.getenv('FRAMES_PER_CHAR_CODE', '2'))
        except Exception:
            base_frames_per_char_code = 2
        frames_per_char_code = max(1, int(base_frames_per_char_code * typing_speed_factor))
        
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
                    draw.text((margin_x, y), q_line, font=font_question, fill=self.colors['keyword'])
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
                        x = margin_x + 50
                        for token, typ in tokens:
                            color = self.colors.get(typ, self.text_color)
                            draw.text((x, cy), token, font=font_code, fill=color)
                            x += draw.textlength(token, font=font_code)
                        cy += 70
                
                # Cursor
                # Compute cursor position considering wrapping of the last line
                last_wrapped = wrap_code_line(draw, current_code_lines[-1], font_code, max_code_width_px)
                last_line_width = draw.textlength(last_wrapped[-1], font=font_code) if last_wrapped else 0
                draw.text((margin_x + 50 + last_line_width, cy - 70), self.cursor_style, font=font_code, fill=self.colors['cursor'])
                
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
        # Slide up terminal
        term_height = 600
        term_y_start = self.height
        term_y_end = self.height - term_height
        
        for i in range(20):
            img, draw = create_bg()
            # Draw static content
            y = question_y
            for q_line in wrapped_question:
                draw.text((margin_x, y), q_line, font=font_question, fill=self.colors['keyword'])
                y += 80
            cy = code_y
            for idx, c_line in enumerate(current_code_lines):
                wrapped_sub = wrap_code_line(draw, c_line, font_code, max_code_width_px)
                for wi, sub in enumerate(wrapped_sub):
                    if wi == 0:
                        line_num = str(idx + 1)
                        draw.text((margin_x, cy), line_num, font=font_code, fill=self.colors['comment'])
                    tokens = self.tokenize_code(sub)
                    x = margin_x + 50
                    for token, typ in tokens:
                        color = self.colors.get(typ, self.text_color)
                        draw.text((x, cy), token, font=font_code, fill=color)
                        x += draw.textlength(token, font=font_code)
                    cy += 70
                
            # Draw Terminal Box
            progress = i / 20
            curr_term_y = term_y_start - (term_height * progress)
            
            draw.rectangle([0, curr_term_y, self.width, self.height], fill=(20, 20, 20))
            draw.rectangle([0, curr_term_y, self.width, curr_term_y + 60], fill=(40, 40, 40)) # Header
            draw.text((margin_x, curr_term_y + 10), "Terminal", font=font_header, fill=self.text_color)
            
            append_frame(img, 1)

        # Waiting State (Blinking Cursor + $)
        base_term_img = last_frame_img.copy() if last_frame_img is not None else Image.new('RGB', (self.width, self.height), self.bg_color)
        prompt_y = term_y_end + 100

        for _ in range(45): # Wait 1.5s
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)

            # Blink cursor
            if _ % 15 < 8:
                draw.text((margin_x, prompt_y), "$ _", font=font_terminal, fill=self.colors['string'])
            else:
                draw.text((margin_x, prompt_y), "$", font=font_terminal, fill=self.colors['string'])

            append_frame(img, 1)

        # Type Command
        command = "node index.js"
        curr_cmd = "$ "
        for char in command:
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)
            curr_cmd += char
            draw.text((margin_x, prompt_y), curr_cmd + "_", font=font_terminal, fill=self.colors['string'])
            append_frame(img, 2) # Slow typing
            
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
            draw.text((margin_x, prompt_y), curr_cmd, font=font_terminal, fill=self.colors['string'])
            
            res_y = prompt_y + 60
            for line in output_lines:
                draw.text((margin_x, res_y), line, font=font_terminal, fill=result_color)
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
                # If ffmpeg merge fails, simply copy temp_video to final output
                os.replace(temp_video, final_output)
        else:
            # If no ffmpeg or audio, just move/copy the video file as final output
            os.replace(temp_video, final_output)
        
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
