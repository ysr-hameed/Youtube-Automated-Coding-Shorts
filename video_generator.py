import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
from pydub import AudioSegment
from pydub.generators import Sine, WhiteNoise
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

    def get_font(self, size, bold=False):
        try:
            # Try to use a good coding font if available, else default
            font_name = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
            return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{font_name}", size)
        except:
            return ImageFont.load_default()

    def create_mechanical_click(self):
        """Synthesize a 'thocky' mechanical keyboard sound"""
        # Mix a short sine wave with some noise for the 'click'
        tone = Sine(400).to_audio_segment(duration=30).apply_gain(-5)
        click = WhiteNoise().to_audio_segment(duration=15).apply_gain(-10)
        sound = tone.overlay(click)
        return sound.fade_out(10)

    def create_enter_sound(self):
        """Synthesize a heavier enter key sound"""
        tone = Sine(300).to_audio_segment(duration=60).apply_gain(-3)
        click = WhiteNoise().to_audio_segment(duration=30).apply_gain(-8)
        sound = tone.overlay(click)
        return sound.fade_out(20)

    def tokenize_code(self, line):
        """Simple regex-based tokenizer for syntax highlighting"""
        tokens = []
        # Regex patterns for syntax
        patterns = [
            (r'(function|const|let|var|return|if|else|for|while|console|log|await|async|import|from)\b', 'keyword'),
            (r'(".*?"|\'.*?\')', 'string'),
            (r'\b(\d+)\b', 'number'),
            (r'(\/\/.*)', 'comment'),
            (r'([+\-*/%=<>!&|]+)', 'operator'),
            (r'(\w+)(?=\()', 'function'), # Word followed by (
            (r'([(){}\[\];,])', 'bracket'),
            (r'(\w+)', 'bracket') # Default identifier
        ]
        
        # Very basic parsing (for demonstration speed)
        # In a real app, we'd iterate char by char or use a lexer
        # Here we'll just split by space and try to match for simplicity in video generation
        # A better approach for video is to just colorize known words
        
        # Let's stick to the previous robust regex method but simplified for this context
        # We will just draw the line character by character in the main loop to ensure perfect typing
        return line

    def generate_video(self, question, code, filename="viral_short"):
        print(f"🚀 Generating Viral Short: {filename}")
        
        # 1. Execute Code to get Real Output
        print("⚙️ Executing code...")
        real_output, return_code = CodeExecutor.run_node(code)
        print(f"📝 Output: {real_output}")

        # 2. Audio Setup (TTS)
        print("🗣️ Generating TTS...")
        tts = gTTS(text=question, lang='en', slow=False)
        tts_path = os.path.join(self.audio_dir, "tts.mp3")
        tts.save(tts_path)
        tts_audio = AudioSegment.from_mp3(tts_path)
        tts_duration_ms = len(tts_audio)
        
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
        
        margin_x = 60
        header_y = 100
        question_y = 200
        code_y = 500 # Start code lower to give space for question
        
        # --- PHASE 1: HEADER & BACKGROUND ---
        def create_bg():
            img = Image.new('RGB', (self.width, self.height), self.bg_color)
            draw = ImageDraw.Draw(img)
            
            # Mac Dots (Huge)
            dot_size = 25
            dot_spacing = 60
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
        
        audio_events = [(0, 'tts', tts_path)]
        
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
            if char.strip():
                time_ms = int((len(frames) / self.fps) * 1000)
                audio_events.append((time_ms, 'click', None))

        # Hold after question
        for _ in range(15): frames.append(frames[-1])

        # --- PHASE 3: CODE TYPING ---
        code_lines = code.split('\n')
        current_code_lines = []
        
        # Faster typing for code (user adjustable, but let's make it snappy)
        frames_per_char_code = 2 
        
        for line_idx, line in enumerate(code_lines):
            current_code_lines.append("")
            
            # Indentation
            indent = len(line) - len(line.lstrip())
            current_code_lines[-1] = " " * indent
            
            for char in line.strip():
                img, draw = create_bg()
                
                # Draw Question (Static)
                y = question_y
                for q_line in wrapped_question:
                    draw.text((margin_x, y), q_line, font=font_question, fill=self.colors['keyword'])
                    y += 80
                
                # Draw Code
                current_code_lines[-1] += char
                
                cy = code_y
                for c_line in current_code_lines:
                    # Simple syntax highlighting (Keyword detection for whole words)
                    # For char-by-char, we just draw the whole line for now to keep it stable
                    # A full lexer for partial lines is complex, so we'll colorize fully typed words
                    # and keep current word white
                    
                    # Draw line number
                    # draw.text((margin_x, cy), "1", font=font_code, fill=self.colors['comment'])
                    
                    # Draw code text
                    draw.text((margin_x + 60, cy), c_line, font=font_code, fill=self.text_color)
                    cy += 70
                
                # Cursor
                last_line_width = draw.textlength(current_code_lines[-1], font=font_code)
                draw.text((margin_x + 60 + last_line_width, cy - 70), self.cursor_style, font=font_code, fill=self.colors['cursor'])
                
                for _ in range(frames_per_char_code):
                    frames.append(img)
                
                if char.strip():
                    time_ms = int((len(frames) / self.fps) * 1000)
                    audio_events.append((time_ms, 'click', None))
            
            # Newline pause
            for _ in range(5): frames.append(frames[-1])

        # Enter Sound after code
        time_ms = int((len(frames) / self.fps) * 1000)
        audio_events.append((time_ms, 'enter', None))
        
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
            for c_line in current_code_lines:
                draw.text((margin_x + 60, cy), c_line, font=font_code, fill=self.text_color)
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
            
            if char.strip():
                time_ms = int((len(frames) / self.fps) * 1000)
                audio_events.append((time_ms, 'click', None))

        # Enter sound
        time_ms = int((len(frames) / self.fps) * 1000)
        audio_events.append((time_ms, 'enter', None))

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
        final_audio = AudioSegment.silent(duration=total_duration)
        
        click_sound = self.create_mechanical_click()
        enter_sound = self.create_enter_sound()
        
        for time_ms, type, data in audio_events:
            if type == 'tts':
                sound = AudioSegment.from_mp3(data)
            elif type == 'click':
                sound = click_sound
            elif type == 'enter':
                sound = enter_sound
            
            final_audio = final_audio.overlay(sound, position=time_ms)
            
        temp_audio = os.path.join(self.audio_dir, "temp_audio.mp3")
        final_audio.export(temp_audio, format="mp3")
        
        # --- MERGE ---
        final_output = os.path.join(self.output_dir, f"{filename}.mp4")
        subprocess.run([
            'ffmpeg', '-y', '-i', temp_video, '-i', temp_audio,
            '-c:v', 'copy', '-c:a', 'aac', final_output
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Cleanup
        os.remove(temp_video)
        os.remove(temp_audio)
        
        return final_output

if __name__ == "__main__":
    gen = ShortsVideoGenerator()
    gen.generate_video(
        "Write a function to check if a number is even",
        "function isEven(n) {\n  return n % 2 === 0;\n}\n\nconsole.log(isEven(4));"
    )
