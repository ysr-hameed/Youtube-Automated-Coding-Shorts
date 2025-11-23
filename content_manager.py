import os
import json
import difflib
import google.generativeai as genai
from database import db

class ContentManager:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        self.languages = ['JavaScript', 'Python', 'Go', 'Java']
        self.lang_idx = 0
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            print("⚠️ GEMINI_API_KEY not found. AI features will use mock data.")
            self.model = None

    def generate_content(self, max_attempts=3):
        """Generate a unique coding question and code using Gemini.
        Returns a content dict on success or None on failure.
        """
        past_topics = db.get_recent_topics(limit=100)
        # Use the current language in the prompt
        lang = self.languages[self.lang_idx % len(self.languages)]
        prompt = f"""
        Generate a unique, viral coding interview question for a YouTube Short.
        Target audience: Beginner to Intermediate programmers.
        Language: {lang}.
        
        Context (DO NOT USE THESE TOPICS):
        {', '.join(past_topics)}
        
    Requirements:
        1. Code must be short (max 10 lines) and visually clean.
        2. Question must be engaging (e.g., "Can you fix this?", "What's the output?").
    2b. Question must be a short hook (no more than 12 words).
        3. Title MUST include 2-3 viral hashtags like #shorts #coding #javascript.
        4. Description must be SEO friendly with keywords.
        
        Return ONLY a JSON object:
        {{
            "topic": "Short topic name",
            "question": "The actual question text",
            "code": "The solution code",
            "title": "Viral Title with #hashtags",
            "description": "SEO Description",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
        
        if not self.model:
            # No AI model configured – do not auto-generate in scheduled mode
            print("⚠️ No AI model configured. Skipping AI generation.")
            return None

        for attempt in range(max_attempts):
            try:
                response = self.model.generate_content(prompt)
                text = response.text.strip()
                if text.startswith('```json'):
                    text = text.replace('```json', '').replace('```', '')
                content = json.loads(text)

                # Validate content fields
                if not content.get('topic') or not content.get('code') or not content.get('question'):
                    print("AI returned incomplete content. Trying again...")
                    continue

                # Ensure the question is short and hook-like (<= 12 words)
                q_words = len(content['question'].split())
                if q_words > 12:
                    print(f"AI returned long question ({q_words} words). Trying again...")
                    continue

                # Avoid obvious duplicate topics using simple matching
                topic_lower = content['topic'].strip().lower()
                duplicate = False
                for t in past_topics:
                    if not t:
                        continue
                    if t.strip().lower() == topic_lower:
                        duplicate = True
                        break
                    # fuzzy similarity
                    ratio = difflib.SequenceMatcher(None, t.strip().lower(), topic_lower).ratio()
                    if ratio > 0.85:
                        duplicate = True
                        break
                if duplicate:
                    print(f"Duplicate or similar topic found (attempt {attempt+1}). Trying again...")
                    # cycle language if we've tried multiple attempts
                    self.lang_idx = (self.lang_idx + 1) % len(self.languages)
                    lang = self.languages[self.lang_idx % len(self.languages)]
                    # rebuild prompt for new language
                    prompt = f"""
        Generate a unique, viral coding interview question for a YouTube Short.
        Target audience: Beginner to Intermediate programmers.
        Language: {lang}.
        
        Context (DO NOT USE THESE TOPICS):
        {', '.join(past_topics)}
        
        Requirements:
        1. Code must be short (max 10 lines) and visually clean.
        2. Question must be engaging (e.g., "Can you fix this?", "What's the output?").
        3. Title MUST include 2-3 viral hashtags like #shorts #coding #javascript.
        4. Description must be SEO friendly with keywords.
        
        Return ONLY a JSON object:
        {{
            "topic": "Short topic name",
            "question": "The actual question text",
            "code": "The solution code",
            "title": "Viral Title with #hashtags",
            "description": "SEO Description",
            "tags": ["tag1", "tag2", "tag3"]
        }}
        """
                    continue

                # All good, store and return (also attach DB id so we can mark as uploaded)
                entry_id = db.add_history(content)
                content['db_id'] = entry_id
                return content
            except Exception as e:
                print(f"Error generating content: {e}. Attempt {attempt+1}/{max_attempts}")
                continue
        # If we reach here, we couldn't generate valid content
        print("AI generation exhausted attempts. Returning None to indicate failure.")
        return None

    def _get_mock_content(self):
        return {
            "topic": "Array Reduce",
            "question": "Write a function to sum an array using reduce()",
            "code": "const nums = [1, 2, 3, 4];\n\nconst sum = nums.reduce((acc, curr) => {\n  return acc + curr;\n}, 0);\n\nconsole.log(sum);",
            "title": "Master Array Reduce in 10 Seconds! 🚀 #shorts #javascript",
            "description": "Learn how to use the reduce method in JavaScript. #shorts #webdev #coding",
            "tags": ["javascript", "coding", "webdev"]
        }
