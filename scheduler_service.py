import time
import schedule
import random
from datetime import datetime
import pytz
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
from publisher import process_and_upload
from database import db
import os

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
        
        # 1. Check daily upload limit
        try:
            daily_limit = int(os.getenv('DAILY_UPLOAD_LIMIT', '1'))
        except Exception:
            daily_limit = 1
        uploaded_today = db.get_today_upload_count() or 0
        if uploaded_today >= daily_limit:
            print(f"⚠️ Daily upload limit reached ({uploaded_today}/{daily_limit}). Skipping.")
            return

        # 2. Generate Content
        content = self.content_mgr.generate_content()
        if not content:
            print("⚠️ Content generation failed or was skipped; will try again later.")
            return

        # 3. Create Video and possibly upload
        result = process_and_upload(content, self.generator, self.youtube_mgr, filename_prefix='daily', auto_upload=(os.getenv('ENABLE_UPLOAD', 'false').lower() == 'true'))
        if result.get('uploaded'):
            print(f"✅ Uploaded video {result.get('youtube_id')}")
        else:
            print("⚠️ Video generated but not uploaded:", result.get('upload_error'))
            
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
