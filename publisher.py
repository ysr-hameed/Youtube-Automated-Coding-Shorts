import os
from database import db

def process_and_upload(content, generator, youtube_mgr, filename_prefix='ai', auto_upload=True):
    """Generate a video using `generator` and optionally upload to YouTube via `youtube_mgr`.
    Returns a dict with keys: success, video_path, uploaded (bool), youtube_id, upload_error.
    """
    if not content:
        return {"success": False, "error": "No content to generate"}

    filename = f"{filename_prefix}_{__import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')}"
    video_path = generator.generate_video(content['question'], content['code'], filename)

    uploaded = False
    youtube_id = None
    upload_error = None
    try:
        if auto_upload and youtube_mgr.is_authenticated():
            try:
                youtube_mgr.authenticate()
                youtube_id = youtube_mgr.upload_video(
                    video_path,
                    content.get('title', filename),
                    content.get('description', ''),
                    content.get('tags', [])
                )
                uploaded = True
            except Exception as e:
                upload_error = str(e)
    except Exception as e:
        upload_error = str(e)

    # Mark db record as uploaded if we have a db_id and upload succeeded
    if uploaded and content.get('db_id'):
        try:
            db.mark_uploaded(entry_id=content['db_id'], youtube_id=youtube_id)
        except Exception:
            pass

    return {
        "success": True,
        "content": content,
        "video_path": video_path,
        "uploaded": uploaded,
        "youtube_id": youtube_id,
        "upload_error": upload_error
    }
