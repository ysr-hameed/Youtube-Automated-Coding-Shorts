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

        # Check audio capabilities
        self.ffmpeg_available = shutil.which('ffmpeg') is not None
        if not PYDUB_AVAILABLE:
            logging.warning("pydub not installed. Audio generation is disabled.")
        if not self.ffmpeg_available:
            logging.warning("ffmpeg not found in PATH. Audio generation is disabled.")

        self.audio_enabled = PYDUB_AVAILABLE and self.ffmpeg_available

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

        # Mix a short sine wave with some noise for the 'click'
        tone = Sine(400).to_audio_segment(duration=30).apply_gain(-5)
        click = WhiteNoise().to_audio_segment(duration=15).apply_gain(-10)
        sound = tone.overlay(click)
        return sound.fade_out(10)

    def create_enter_sound(self):
        """Synthesize a heavier enter key sound"""
        if not self.audio_enabled:
            return None

        tone = Sine(300).to_audio_segment(duration=60).apply_gain(-3)
        click = WhiteNoise().to_audio_segment(duration=30).apply_gain(-8)
        sound = tone.overlay(click)
        return sound.fade_out(20)

    def create_background_music(self, duration_ms):
        """Create a low-volume ambient background music layer for the whole video.
        Use multiple sine waves slightly detuned to make it interesting.
        """
        if not self.audio_enabled:
            return None

        # Create a layered ambient track
        base = Sine(220).to_audio_segment(duration=duration_ms).apply_gain(-30)
        layer1 = Sine(330).to_audio_segment(duration=duration_ms).apply_gain(-34)
        layer2 = Sine(440).to_audio_segment(duration=duration_ms).apply_gain(-36)
        music = base.overlay(layer1).overlay(layer2)

        # Add a faint noise pad for texture
        noise = WhiteNoise().to_audio_segment(duration=duration_ms).apply_gain(-42)
        music = music.overlay(noise)
        return music

    def create_background_music(self, duration_ms=10000):
        """Create a subtle looping background music segment for the full video duration.
        This uses layered low-volume sine tones and light noise for texture.
        """
        if not self.audio_enabled:
            return None

        # Build a layered pad/chord with low gain
        base1 = Sine(110).to_audio_segment(duration=duration_ms).apply_gain(-30)
        base2 = Sine(220).to_audio_segment(duration=duration_ms).apply_gain(-33)
        base3 = Sine(330).to_audio_segment(duration=duration_ms).apply_gain(-35)
        # A faint noise bed
        noise = WhiteNoise().to_audio_segment(duration=duration_ms).apply_gain(-50)
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
        total_chars_question = len(question)
        ms_per_char_question = tts_duration_ms / max(1, total_chars_question)
        frames_per_char_question = max(1, int((ms_per_char_question / 1000) * self.fps))

        frames = []
        
        # --- VISUAL CONFIG ---
        # Huge Fonts
        font_code = self.get_font(48) 
        font_question = self.get_font(55, bold=True)
        font_header = self.get_font(40)
        font_terminal = self.get_font(42)
        
        margin_x = 32
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
            small_font = self.get_font(28)
            draw.text((self.width//2 + 40, header_y + 6), "ViralShorts AI", font=small_font, fill=self.colors['comment'])
            return img, draw

        # --- PHASE 2: QUESTION TYPING (Synced with TTS) ---
        wrapped_question = textwrap.wrap(question, width=25) # Narrow width for huge text
        
        current_q_text = ""
        q_char_count = 0
        
        audio_events = []
        if tts_path:
            audio_events.append((0, 'tts', tts_path))
        
        # Flatten wrapped lines for typing calculation
        flat_question = "\n".join(wrapped_question)
        
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
            
            # Add frames
            for _ in range(frames_per_char_question):
                frames.append(img)
            
            # Key sound
            # omit click sound events to avoid keyboard noise

        # Hold after question
        for _ in range(15): frames.append(frames[-1])

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
        
        # Faster typing for code (user adjustable, but let's make it snappy)
        frames_per_char_code = 2 
        
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
                
                for _ in range(frames_per_char_code):
                    frames.append(img)
                
                # omit click sound events to avoid keyboard noise
            
            # Newline pause
            for _ in range(5): frames.append(frames[-1])

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
            
            frames.append(img)

        # Waiting State (Blinking Cursor + $)
        base_term_img = frames[-1].copy()
        prompt_y = term_y_end + 100
        
        for _ in range(45): # Wait 1.5s
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)
            
            # Blink cursor
            if _ % 15 < 8:
                draw.text((margin_x, prompt_y), "$ _", font=font_terminal, fill=self.colors['string'])
            else:
                draw.text((margin_x, prompt_y), "$", font=font_terminal, fill=self.colors['string'])
                
            frames.append(img)

        # Type Command
        command = "node index.js"
        curr_cmd = "$ "
        for char in command:
            img = base_term_img.copy()
            draw = ImageDraw.Draw(img)
            curr_cmd += char
            draw.text((margin_x, prompt_y), curr_cmd + "_", font=font_terminal, fill=self.colors['string'])
            frames.append(img)
            frames.append(img) # Slow typing
            

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
                
            frames.append(img)

        # --- RENDER VIDEO ---
        print(f"🎥 Rendering {len(frames)} frames...")
        temp_video = os.path.join(self.output_dir, "temp_vid.mp4")
        out = cv2.VideoWriter(temp_video, cv2.VideoWriter_fourcc(*'mp4v'), self.fps, (self.width, self.height))
        
        for frame in frames:
            out.write(cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR))
        out.release()

        # --- MIX AUDIO ---
        print("🎵 Mixing Audio...")
        total_duration = len(frames) / self.fps * 1000
        if self.audio_enabled:
            final_audio = AudioSegment.silent(duration=total_duration)
            # Add gentle background music for the entire video
            bg_music = self.create_background_music(total_duration)
            if bg_music is not None:
                final_audio = final_audio.overlay(bg_music)
        else:
            final_audio = None
        
        click_sound = self.create_mechanical_click()
        # Make clicks a bit softer so background music sits under them
        if click_sound is not None:
            click_sound = click_sound.apply_gain(-6)
        enter_sound = self.create_enter_sound()
        
        # If audio is not enabled, skip mixing entirely
        if self.audio_enabled:
            for time_ms, type, data in audio_events:
                try:
                    if type == 'tts' and data:
                        sound = AudioSegment.from_mp3(data)
                    elif type == 'click':
                        sound = click_sound
                    elif type == 'enter':
                        sound = enter_sound
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
