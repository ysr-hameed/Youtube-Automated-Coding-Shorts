import time
import schedule
import random
from datetime import datetime, timedelta
import pytz
from video_generator import ShortsVideoGenerator
from content_manager import ContentManager
from youtube_manager import YouTubeManager
from publisher import process_and_upload
from database import db
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError

class AutoScheduler:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Kolkata')
        self.generator = ShortsVideoGenerator()
        self.content_mgr = ContentManager()
        self.youtube_mgr = YouTubeManager()
        self.last_upload_time = None

    # The scheduler executes scheduled entries found in the DB via start()

    def _generate_daily_schedule(self, count=1):
        """Create schedule entries for the current day, ensuring at least a 30 minute gap between runs.
        If schedules already exist for today, don't duplicate them. Return list of schedule dicts.
        """
        today = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        existing = db.get_schedule_for_day(today)
        if existing and len(existing) >= count:
            return existing

        # window start and end
        # Check for explicit times via env var (comma-separated HH:MM values in IST)
        times_env = os.getenv('DAILY_SCHEDULE_TIMES')
        if times_env:
            times_list = [t.strip() for t in times_env.split(',') if t.strip()]
            scheduled = []
            for t in times_list:
                try:
                    hh, mm = [int(x) for x in t.split(':')]
                    scheduled_time = today + timedelta(hours=hh, minutes=mm)
                    # Persist schedule in DB if not existing
                    sid = db.add_schedule(scheduled_time)
                    scheduled.append({ 'id': sid, 'scheduled_at': scheduled_time, 'executed': False })
                except Exception:
                    continue
            for s in scheduled:
                print(f"🗓️ Scheduled (explicit): {s.get('scheduled_at').isoformat()} (id: {s.get('id')})")
            return scheduled

        window_start = today + timedelta(hours=8)  # 8:00 IST
        window_end = today + timedelta(hours=21)   # 21:00 IST
        total_minutes = int((window_end - window_start).total_seconds() // 60)
        # If count is more than feasible with 30 minute gaps, we still distribute evenly
        if count <= 0:
            count = 1
        # Ensure minimum 30 minute gap
        max_count = total_minutes // 30
        if count > max_count and max_count > 0:
            count = max_count
        segment = total_minutes // count
        rand = random.Random()
        rand.seed(time.time_ns())
        scheduled = []
        for i in range(count):
            seg_start_min = i * segment
            seg_end_min = seg_start_min + segment - 1
            if seg_end_min <= seg_start_min:
                seg_end_min = seg_start_min + 1
            offset_min = rand.randint(seg_start_min, seg_end_min)
            scheduled_time = window_start + timedelta(minutes=offset_min)
            # Persist schedule in DB
            sid = db.add_schedule(scheduled_time)
            scheduled.append({ 'id': sid, 'scheduled_at': scheduled_time, 'executed': False })
        # Log created schedule times
        for s in scheduled:
            print(f"🗓️ Scheduled: {s.get('scheduled_at').isoformat()} (id: {s.get('id')})")
        return scheduled

    def start(self):
        print("🕰️ Scheduler Started (India Time)")
        # On start, ensure today's schedule exists based on env var DAILY_SCHEDULES
        try:
            count = int(os.getenv('DAILY_SCHEDULES', '1'))
        except Exception:
            count = 1
        self._generate_daily_schedule(count)
    # Run main loop checking schedule every 60 seconds
        while True:
            # Regen schedule at start of new day
            today_date = datetime.now(self.tz).date()
            if getattr(self, 'current_day', None) != today_date:
                self.current_day = today_date
                self._generate_daily_schedule(count)
            # Fetch today's schedules
            today = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
            schedules = db.get_schedule_for_day(today) or []
            now = datetime.now(self.tz)
            for s in schedules:
                try:
                    if not s.get('executed') and s.get('scheduled_at') <= now:
                        # Run a scheduled job
                        print(f"⏰ Running scheduled job for {s.get('scheduled_at')}")
                        # Check daily upload limit before starting the work
                        try:
                            daily_limit = int(os.getenv('DAILY_UPLOAD_LIMIT', '1'))
                        except Exception:
                            daily_limit = 1
                        uploaded_today = db.get_today_upload_count() or 0
                        if uploaded_today >= daily_limit:
                            print(f"⚠️ Daily upload limit reached ({uploaded_today}/{daily_limit}). Skipping scheduled job.")
                            db.mark_schedule_executed(s.get('id'), executed_at=now, result={'success': False, 'error': 'daily upload limit reached'})
                            continue

                        # Use a timeout for generation/upload because jobs can take long
                        timeout_seconds = int(os.getenv('SCHEDULE_TIMEOUT_SECONDS', '600'))
                        def run_job():
                            content = self.content_mgr.generate_content()
                            if not content:
                                return {'success': False, 'error': 'AI generation failed'}
                            # Ensure content exists in DB
                            entry_id = db.add_history({
                                'topic': content['topic'],
                                'question': content['question'],
                                'code': content['code'],
                                'title': content.get('title'),
                                'tags': content.get('tags', [])
                            })
                            content['db_id'] = entry_id
                            auto_upload_flag = os.getenv('ENABLE_UPLOAD', 'true').lower() == 'true'
                            result = process_and_upload(content, self.generator, self.youtube_mgr, filename_prefix='scheduled', auto_upload=auto_upload_flag)
                            return result
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(run_job)
                            try:
                                result = future.result(timeout=timeout_seconds)
                            except TimeoutError:
                                # Mark schedule executed with timeout result
                                db.mark_schedule_executed(s.get('id'), executed_at=now, result={'success': False, 'error': 'timeout', 'timeout': True})
                                print('⏳ Scheduled job timed out; marked as failed')
                                continue
                        # If scheduled run returned but was not successful due to daily limit or other external skip, mark accordingly
                        if isinstance(result, dict) and not result.get('success'):
                            db.mark_schedule_executed(s.get('id'), executed_at=now, result=result)
                            continue
                        # Mark schedule executed with result
                        db.mark_schedule_executed(s.get('id'), executed_at=now, result={'success': result.get('success', False), 'uploaded': result.get('uploaded', False), 'youtube_id': result.get('youtube_id'), 'error': result.get('upload_error')})
                except Exception as e:
                    print('⚠️ Error running scheduled job', e)
            time.sleep(60)

if __name__ == "__main__":
    import os
    scheduler = AutoScheduler()
    scheduler.start()
