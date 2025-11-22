"""
Preview generated keyboard clicks and enter sound without building a full video.
Run this script to produce sample audio files in the audio/ directory.
"""
import os
from video_generator import ShortsVideoGenerator

def main():
    g = ShortsVideoGenerator()
    if not g.audio_enabled:
        print("Audio not enabled - ensure pydub and ffmpeg are installed and available on PATH")
        return
    os.makedirs('audio', exist_ok=True)
    # Generate few variants
    click = g.create_mechanical_click()
    if click:
        click.export('audio/preview_mechanical_click.mp3', format='mp3')
        print('Wrote audio/preview_mechanical_click.mp3')
    rand_click = g.create_random_key_click()
    if rand_click:
        rand_click.export('audio/preview_random_click.mp3', format='mp3')
        print('Wrote audio/preview_random_click.mp3')
    enter = g.create_enter_sound()
    if enter:
        enter.export('audio/preview_enter.mp3', format='mp3')
        print('Wrote audio/preview_enter.mp3')

if __name__ == '__main__':
    main()
