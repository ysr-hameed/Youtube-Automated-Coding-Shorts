import os
import json
import pickle
import base64
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from database import db

class YouTubeManager:
    def __init__(self):
        self.SCOPES = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube',
            'https://www.googleapis.com/auth/youtube.force-ssl'
        ]
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.youtube = None

    def _get_client_secrets(self):
        """Construct client config from environment variables.
        The function prefers the values stored in the DB (if any),
        otherwise falls back to the GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
        variables from the .env file. The constructed JSON is saved back to the
        DB so subsequent runs can reuse it without re‑reading the env.
        """
        # 1. Try getting full config from DB (previously saved)
        secrets = db.get_config('client_secrets')
        if secrets:
            return json.loads(secrets)

        # 2. Build config from env vars (required for this project)
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if client_id and client_secret:
            config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost:8080/"]
                }
            }
            # Save constructed config to DB for future runs
            db.set_config('client_secrets', json.dumps(config))
            return config

        # 3. If neither DB nor env vars are available, return None
        return None
        # 1. Try getting full config from DB
        secrets = db.get_config('client_secrets')
        if secrets:
            return json.loads(secrets)
            
        # 2. Try Full JSON from ENV
        secrets_env = os.getenv("GOOGLE_CLIENT_SECRETS")
        if secrets_env:
            db.set_config('client_secrets', secrets_env)
            return json.loads(secrets_env)
            
        # 3. Try Simple ID/Secret from ENV (Easier for user)
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        if client_id and client_secret:
            config = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost:8080/"]
                }
            }
            # Save constructed config to DB
            db.set_config('client_secrets', json.dumps(config))
            return config
            
        # 4. Try File
        if os.path.exists("client_secrets.json"):
            with open("client_secrets.json", 'r') as f:
                content = f.read()
                db.set_config('client_secrets', content)
                return json.loads(content)
                
        return None

    def _save_credentials(self, creds):
        # Pickle and base64 encode to store in text field
        pickled = base64.b64encode(pickle.dumps(creds)).decode('utf-8')
        db.set_config('youtube_token', pickled)
        # Also store a basic json shape for human inspection and migration
        try:
            cred_json = {
                'token': getattr(creds, 'token', None),
                'refresh_token': getattr(creds, 'refresh_token', None),
                'token_uri': getattr(creds, 'token_uri', None),
                'client_id': getattr(creds, 'client_id', None),
                'client_secret': getattr(creds, 'client_secret', None),
                'scopes': list(getattr(creds, 'scopes', [])) if getattr(creds, 'scopes', None) else None
            }
            db.set_config('youtube_token_json', json.dumps(cred_json))
        except Exception:
            pass

    def _load_credentials(self):
        token = db.get_config('youtube_token')
        if token:
            return pickle.loads(base64.b64decode(token))
        return None

    def authenticate(self):
        """Authenticate and save tokens to DB"""
        creds = self._load_credentials()
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing Access Token...")
                creds.refresh(Request())
            else:
                print("🆕 Starting New Auth Flow...")
                client_config = self._get_client_secrets()
                if not client_config:
                    print("❌ No client secrets found (DB, ENV, or file). Cannot auth.")
                    return False
                    
                # Create flow from config dictionary
                flow = InstalledAppFlow.from_client_config(client_config, self.SCOPES)
                # Use fixed port 8080 to match Google Console Redirect URI
                # Request offline access plus consent to get a refresh token
                try:
                    creds = flow.run_local_server(port=8080, access_type='offline', prompt='consent')
                except TypeError:
                    creds = flow.run_local_server(port=8080)
                
            self._save_credentials(creds)
                
        self.youtube = build(self.api_service_name, self.api_version, credentials=creds)
        return True

    def is_authenticated(self):
        """Return a boolean indicating whether we have (and can use) saved credentials.

        This will try to load credentials from the DB and report whether they are
        present and usable. We do not trigger a login flow here.
        """
        creds = self._load_credentials()
        if not creds:
            return False
        try:
            if creds.valid:
                return True
            # If expired but refresh token exists, we can still refresh programmatically
            if getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
                # Attempt a quiet refresh
                try:
                    creds.refresh(Request())
                    # Save the refreshed credentials
                    self._save_credentials(creds)
                    return True
                except Exception:
                    return False
            return False
        except Exception:
            return False

    def upload_video(self, file_path, title, description, tags, category_id="28"):
        if not self.youtube:
            if not self.authenticate():
                return None

        body = {
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        
        print(f"📤 Uploading to YouTube: {title}")
        request = self.youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   Progress: {int(status.progress() * 100)}%")
                
        print(f"✅ Upload Complete! Video ID: {response.get('id')}")
        return response.get('id')
