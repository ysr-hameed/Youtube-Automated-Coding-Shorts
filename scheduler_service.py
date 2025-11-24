import time
try:
    import schedule
except Exception:
    schedule = None
import random
from datetime import datetime, timedelta
try:
    import pytz
except Exception:
    pytz = None
try:
    from video_generator import ShortsVideoGenerator
except Exception:
    ShortsVideoGenerator = None
from content_manager import ContentManager
from youtube_manager import YouTubeManager
from publisher import process_and_upload
from database import db
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError

class AutoScheduler:
    def __init__(self):
        self.tz = pytz.timezone('Asia/Kolkata')
        self.generator = ShortsVideoGenerator() if ShortsVideoGenerator else None
        self.content_mgr = ContentManager()
        self.youtube_mgr = YouTubeManager()
        self.last_upload_time = None

    # The scheduler executes scheduled entries found in the DB via start()

    def _generate_daily_schedule(self, count=1):
        """Create schedule entries for the current day, ensuring at least a 30 minute gap between runs.
        If schedules already exist for today, add more if needed. Return list of schedule dicts.
        """
        if pytz:
            today = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            today = datetime.now(self.tz).replace(hour=0, minute=0, second=0, microsecond=0)
        now = datetime.now(self.tz) if pytz else datetime.now()
        # Clean up old schedules
        try:
            deleted_old = db.delete_schedules_before_day(today)
            if deleted_old > 0:
                print(f"🗑️ Deleted {deleted_old} old schedules")
        except Exception as e:
            print(f"⚠️ Failed to delete old schedules: {e}")
        existing = db.get_schedule_for_day(today)
        existing_times = [s['scheduled_at'] for s in existing]
        existing_future_times = [et for et in existing_times if et > now]
        count = min(count, 7)
        needed = count - len(existing)
        print(f"📅 Today: {today}, Existing schedules: {len(existing)}, Needed: {needed} at {datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S IST')}")
        if needed <= 0:
            return existing
        
        # Create additional schedules

        # window start and end
        # Check for explicit times via env var (comma-separated HH:MM values in IST)
        times_env = os.getenv('DAILY_SCHEDULE_TIMES')
        if times_env:
            times_list = [t.strip() for t in times_env.split(',') if t.strip()]
            scheduled = []
            # Parse provided explicit times and apply min gap constraint
            parsed_times = []
            for t in times_list:
                try:
                    hh, mm = [int(x) for x in t.split(':')]
                    dt = today + timedelta(hours=hh, minutes=mm)
                    parsed_times.append(dt)
                except Exception:
                    continue
            parsed_times = sorted(parsed_times)
            # Enforce min_gap_minutes between explicit times
            try:
                min_gap_minutes = int(os.getenv('DAILY_MIN_GAP_MINUTES', '30'))
            except Exception:
                min_gap_minutes = 30
            last_added = None
            for t in times_list:
                try:
                    hh, mm = [int(x) for x in t.split(':')]
                    scheduled_time = today + timedelta(hours=hh, minutes=mm)
                    # Skip if already exists
                    if scheduled_time in existing_times:
                        continue
                    # Skip times less than min gap from the last added time
                    if last_added and (scheduled_time - last_added).total_seconds() < min_gap_minutes * 60:
                        logging.warning(f"Explicit schedule {scheduled_time.isoformat()} too close to previous schedule; skipped (min gap {min_gap_minutes}m)")
                        continue
                    sid = db.add_schedule(scheduled_time)
                    scheduled.append({ 'id': sid, 'scheduled_at': scheduled_time, 'executed': False })
                    last_added = scheduled_time
                except Exception:
                    continue
            for s in scheduled:
                print(f"🗓️ Scheduled (explicit): {s.get('scheduled_at').isoformat()} (id: {s.get('id')})")
            return existing + scheduled

        # If we're generating schedule during runtime, avoid creating times in the past for today
        now = datetime.now(self.tz) if pytz else datetime.now()
        # By default prefer not to create schedules in the past, but allow forcing full-day schedule
        try:
            allow_past = os.getenv('DAILY_ALLOW_PAST', 'true').lower() in ('1', 'true', 'yes')
        except Exception:
            allow_past = True

        if allow_past:
            window_start = today + timedelta(hours=8)
        else:
            window_start = max(today + timedelta(hours=8), now + timedelta(minutes=1))  # 8:00 IST or now+1m
        window_end = today + timedelta(hours=20)   # 20:00 IST (exclusive end time for production schedule window)

        # If the computed window is invalid (end <= start), fall back to full-day window to ensure schedules are created
        if window_end <= window_start:
            window_start = today + timedelta(hours=8)
            window_end = today + timedelta(hours=20)
        total_minutes = int((window_end - window_start).total_seconds() // 60)
        # Determine minimum gap minutes and ensure count is valid
        try:
            min_gap_minutes = int(os.getenv('DAILY_MIN_GAP_MINUTES', '90'))
        except Exception:
            min_gap_minutes = 90
        if count <= 0:
            count = 1
        # Ensure minimum gap
        max_count = total_minutes // min_gap_minutes
        if count > max_count and max_count > 0:
            count = max_count
        segment = total_minutes // count
        rand = random.Random()
        rand.seed(time.time_ns())
        scheduled = []
        loop_count = needed if 'needed' in locals() else count
        for i in range(loop_count):
            seg_start_min = i * segment
            seg_end_min = seg_start_min + segment - 1
            if seg_end_min <= seg_start_min:
                seg_end_min = seg_start_min + 1
            offset_min = rand.randint(seg_start_min, seg_end_min)
            scheduled_time = window_start + timedelta(minutes=offset_min)
            # If scheduled time is already too close to now (shouldn't happen because window_start uses now), skip
            if (scheduled_time - now).total_seconds() < 0:
                continue
            # Skip if already exists
            if scheduled_time in existing_times:
                continue
            # Persist schedule in DB
            sid = db.add_schedule(scheduled_time)
            scheduled.append({ 'id': sid, 'scheduled_at': scheduled_time, 'executed': False })
        # Log created schedule times
        for s in scheduled:
            print(f"🗓️ Scheduled: {s.get('scheduled_at').strftime('%Y-%m-%d %H:%M:%S IST')} (id: {s.get('id')})")
        print(f"✅ Generated {len(scheduled)} new schedules at {datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S IST')}")
        return existing + scheduled

    def start(self):
        # Print DB status and scheduler start info to aid debugging
        try:
            db_status = db.get_status()
        except Exception:
            db_status = {'connected': False}
        print(f"🕰️ Scheduler Started (India Time) at {datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S IST')} | DB connected={db_status.get('connected')}")
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
                        print(f"⏰ Running scheduled job for {s.get('scheduled_at').strftime('%Y-%m-%d %H:%M:%S IST')} at {datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S IST')}")
                        # If a scheduled job is older than allowable 'miss' window we skip it to avoid re-running on restart
                        try:
                            allow_missed_seconds = int(os.getenv('SCHEDULE_ALLOW_MISSED_SECONDS', '300'))
                        except Exception:
                            allow_missed_seconds = 300
                        if (now - s.get('scheduled_at')).total_seconds() > allow_missed_seconds:
                            # mark as missed
                            db.mark_schedule_executed(s.get('id'), executed_at=now, result={'success': False, 'error': 'missed'})
                            print(f"⚠️ Scheduled job {s.get('id')} missed window; skipping")
                            continue
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
                            current_time = datetime.now(self.tz).strftime('%Y-%m-%d %H:%M:%S IST')
                            print(f"🤖 [{current_time}] Starting AI content generation for scheduled job")
                            content = self.content_mgr.generate_content()
                            if not content:
                                print(f"❌ [{current_time}] AI generation failed - no content")
                                return {'success': False, 'error': 'AI generation failed'}
                            print(f"✅ [{current_time}] AI generated content: {content.get('question', 'N/A')[:50]}...")
                            # Ensure content exists in DB
                            entry_id = db.add_history({
                                'topic': content['topic'],
                                'question': content['question'],
                                'code': content['code'],
                                'title': content.get('title'),
                                'tags': content.get('tags', [])
                            })
                            content['db_id'] = entry_id
                            print(f"🎥 [{current_time}] Starting video generation")
                            auto_upload_flag = os.getenv('ENABLE_UPLOAD', 'true').lower() == 'true'
                            result = process_and_upload(content, self.generator, self.youtube_mgr, filename_prefix='scheduled', auto_upload=auto_upload_flag)
                            print(f"📤 [{current_time}] Video generation/upload result: success={result.get('success')}, uploaded={result.get('uploaded')}, error={result.get('upload_error')}")
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
