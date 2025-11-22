import os
import json
import google.generativeai as genai
from database import db

class ContentManager:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            print("⚠️ GEMINI_API_KEY not found. AI features will use mock data.")
            self.model = None

    def generate_content(self):
        """Generate a unique coding question and code using Gemini"""
        # Get context from DB
        past_topics = db.get_recent_topics(limit=50)
        
        prompt = f"""
        Generate a unique, viral coding interview question for a YouTube Short.
        Target audience: Beginner to Intermediate programmers.
        Language: JavaScript (Node.js).
        
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
        
        if not self.model:
            return self._get_mock_content()
            
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip()
            if text.startswith('```json'):
                text = text.replace('```json', '').replace('```', '')
            
            content = json.loads(text)
            
            # Save to DB
            db.add_history(content)
            
            return content
        except Exception as e:
            print(f"Error generating content: {e}")
            return self._get_mock_content()

    def _get_mock_content(self):
        return {
            "topic": "Array Reduce",
            "question": "Write a function to sum an array using reduce()",
            "code": "const nums = [1, 2, 3, 4];\n\nconst sum = nums.reduce((acc, curr) => {\n  return acc + curr;\n}, 0);\n\nconsole.log(sum);",
            "title": "Master Array Reduce in 10 Seconds! 🚀 #shorts #javascript",
            "description": "Learn how to use the reduce method in JavaScript. #shorts #webdev #coding",
            "tags": ["javascript", "coding", "webdev"]
        }
