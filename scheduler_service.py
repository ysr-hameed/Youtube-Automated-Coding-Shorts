import time
import schedule
import random
from datetime import datetime
import pytz
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager

class AutoScheduler:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Kolkata')
        self.generator = ShortsVideoGenerator()
        self.content_mgr = ContentManager()
        self.youtube_mgr = YouTubeManager()
        self.last_upload_time = None

    def job(self):
        now = datetime.now(self.tz)
        
        # Check time window (8 AM - 10 PM)
        if not (8 <= now.hour < 22):
            print(f"💤 Outside active hours ({now.strftime('%H:%M')}). Skipping.")
            return

        # Check interval (at least 3 hours)
        if self.last_upload_time:
            elapsed = (now - self.last_upload_time).total_seconds() / 3600
            if elapsed < 3:
                print(f"⏳ Too soon since last upload ({elapsed:.1f}h ago). Waiting.")
                return

        print("🎬 Starting Scheduled Job...")
        
        # 1. Generate Content
        content = self.content_mgr.generate_content()
        
        # 2. Create Video
        filename = f"daily_{now.strftime('%Y%m%d_%H%M')}"
        video_path = self.generator.generate_video(
            content['question'],
            content['code'],
            filename
        )
        
        # 3. Upload
        if os.getenv("ENABLE_UPLOAD", "false").lower() == "true":
            self.youtube_mgr.upload_video(
                video_path,
                content['title'],
                content['description'],
                content['tags']
            )
        else:
            print("⚠️ Upload disabled in ENV. Video saved locally.")
            
        self.last_upload_time = now

    def start(self):
        print("🕰️ Scheduler Started (India Time)")
        
        # Schedule checks every hour
        schedule.every(1).hours.do(self.job)
        
        # Also run once immediately for testing if requested
        # self.job() 
        
        while True:
            schedule.run_pending()
            time.sleep(60)

if __name__ == "__main__":
    import os
    scheduler = AutoScheduler()
    scheduler.start()
