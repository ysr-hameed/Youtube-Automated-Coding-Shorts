import os
import json
import difflib
import random
import google.generativeai as genai
from database import db


class ContentManager:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.languages = ["JavaScript", "Python", "Go", "Java", "C++"]
        if self.api_key:
            genai.configure(api_key=self.api_key)
            # model wrapper
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            print("⚠️ GEMINI_API_KEY not found. AI features will use mock data.")
            self.model = None

    def generate_content(self, max_attempts=3):
        """Generate a unique coding question and code using Gemini.
        Returns a content dict on success or None on failure.
        """
        lang_map = {
            "JavaScript": "javascript",
            "Python": "python",
            "Go": "go",
            "Java": "java",
            "C++": "cpp",
        }

        # Pick an initial language at random
        lang = random.choice(self.languages)
        lang_id = lang_map.get(lang, lang.lower())

        # Helper to build the prompt for a given language and recent context
        def build_prompt(language, past_topics, recent_snippets):
            """Construct a strict JSON-only prompt that instructs the model to return a single
            JSON object (no prose, no markdown, no surrounding backticks) matching the schema.
            """
            recent_block = "\n".join(recent_snippets) if recent_snippets else "(none)"
            topics_block = ", ".join(past_topics) if past_topics else "(none)"

            # JSON schema and example to reduce hallucinations and incomplete responses
            schema = {
                "type": "object",
                "required": ["topic", "question", "code", "output", "title", "description", "tags", "thumbnail_prompt", "seo_keywords"],
                "properties": {
                    "topic": {"type": "string", "description": "Short topic title (3-6 words)"},
                    "question": {"type": "string", "description": "Hook question <= 12 words"},
                    "code": {"type": "string", "description": "Code snippet, max 10 lines"},
                    "output": {"type": "string", "description": "Expected program output (max 5 lines)"},
                    "title": {"type": "string", "description": "YouTube title with 2-3 hashtags"},
                    "description": {"type": "string", "description": "SEO-friendly description"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "thumbnail_prompt": {"type": "string", "description": "A short phrase to generate a thumbnail image concept for the video"},
                    "seo_keywords": {"type": "array", "items": {"type": "string"}, "description": "Short list of 3-5 SEO keyword phrases to include in description/tags"}
                }
            }

            example = {
                "topic": "Array Sum (reduce)",
                "question": "Can you sum an array with reduce()?",
                "code": "const nums = [1,2,3,4];\nconst sum = nums.reduce((a,b)=>a+b,0);\nconsole.log(sum);",
                "output": "10",
                "title": "Sum an Array in One Line — Reduce() Hack! #shorts #javascript",
                "description": "Learn how to quickly sum an array using Array.prototype.reduce in JavaScript — quick, clear, and beginner-friendly. #shorts",
                "tags": ["javascript","shorts","coding"]
                ,"thumbnail_prompt": "A minimal overlay showing small array numbers inside a jar with a bright action arrow",
                "seo_keywords": ["javascript reduce", "sum array reduce", "array reduce tutorial"]
            }

            prompt_lines = [
                "You are an assistant that MUST return exactly one JSON object and nothing else.",
                "Do NOT include any markdown, commentary, explanation, or surrounding backticks.",
                f"Target audience: Beginner to Intermediate programmers. Language: {language}.",
                "Do NOT reuse or repeat topics found in the 'Recent videos' list below. Avoid duplicates.",
                "Code rules: max 10 non-empty lines, keep it concise and display-friendly.",
                "Question rules: A short engaging hook <= 12 words (examples: \"What's the output?\", \"Can you fix this?\").",
                "Output rules: Provide the exact expected stdout output when the snippet is run, max 5 lines.",
                "Title rules: Create a high-CTR title (40-60 characters) that includes 1-2 viral hashtags and a strong hook — adrenalized verbs are good (e.g., 'Master', 'Fixed', 'One Line').",
                "Description rules: 80-160 characters, SEO-optimized, include primary SEO keywords and a short CTA.",
                "Thumbnail rules: Provide a short thumbnail prompt for an eye-catching image that fits the short format.",
                "Return schema: Use the following JSON schema and follow the example exactly."
            ]

            prompt = "\n".join(prompt_lines) + "\n\n"
            prompt += "RECENT VIDEOS (do not reuse these topics):\n" + recent_block + "\n\n"
            prompt += "RECENT TOPICS (avoid):\n" + topics_block + "\n\n"
            prompt += "JSON_SCHEMA:\n" + json.dumps(schema, indent=2) + "\n\n"
            prompt += "EXAMPLE_RESPONSE (must follow exactly):\n" + json.dumps(example, indent=2) + "\n\n"
            prompt += "Return only the JSON object now. If you cannot produce a valid object, return an empty JSON object {}."
            return prompt

        # Gather per-language context from DB (graceful if schema doesn't support language)
        try:
            past_topics = db.get_recent_topics(limit=100, language=lang_id) or []
        except Exception:
            past_topics = db.get_recent_topics(limit=100) or []

        try:
            recent_history = db.get_recent_history(limit=10, language=lang_id) or []
        except Exception:
            recent_history = []

        recent_snippets = []
        for h in recent_history[:5]:
            code_snip = h.get("code", "")
            first_line = next((l for l in code_snip.splitlines() if l.strip()), "")
            if len(first_line) > 120:
                first_line = first_line[:117] + "..."
            recent_snippets.append(f"{h.get('topic')} -> {first_line}")

        prompt = build_prompt(lang, past_topics, recent_snippets)

        # If no model configured, do NOT use mock content in production: return None
        if not self.model:
            print("⚠️ No AI model configured. Skipping AI generation (no mock).")
            return None

        for attempt in range(1, max_attempts + 1):
            try:
                resp = self.model.generate_content(prompt)
                text = getattr(resp, "text", "") or str(resp)
                text = text.strip()
                if text.startswith("```json"):
                    text = text.replace("```json", "").replace("```", "").strip()

                content = json.loads(text)

                # basic validation
                if not content.get("topic") or not content.get("code") or not content.get("question") or not content.get("output"):
                    print(f"AI returned incomplete content (attempt {attempt}). Retrying...")
                    continue

                # enforce short hook requirement
                q_words = len(content["question"].split())
                if q_words > 12:
                    print(f"AI returned long question ({q_words} words) on attempt {attempt}. Retrying...")
                    continue

                # duplicate detection against recent topics
                topic_lower = content["topic"].strip().lower()
                duplicate = False
                for t in past_topics:
                    if not t:
                        continue
                    t_lower = t.strip().lower()
                    if t_lower == topic_lower:
                        duplicate = True
                        break
                    ratio = difflib.SequenceMatcher(None, t_lower, topic_lower).ratio()
                    if ratio > 0.85:
                        duplicate = True
                        break

                if duplicate:
                    print(f"Duplicate or very similar topic detected on attempt {attempt}. Trying a different language.")
                    # switch language and rebuild context/prompt
                    other_langs = [l for l in self.languages if l != lang]
                    if not other_langs:
                        continue
                    lang = random.choice(other_langs)
                    lang_id = lang_map.get(lang, lang.lower())
                    try:
                        past_topics = db.get_recent_topics(limit=100, language=lang_id) or []
                    except Exception:
                        past_topics = db.get_recent_topics(limit=100) or []
                    try:
                        recent_history = db.get_recent_history(limit=10, language=lang_id) or []
                    except Exception:
                        recent_history = []

                    recent_snippets = []
                    for h in recent_history[:5]:
                        code_snip = h.get("code", "")
                        first_line = next((l for l in code_snip.splitlines() if l.strip()), "")
                        if len(first_line) > 120:
                            first_line = first_line[:117] + "..."
                        recent_snippets.append(f"{h.get('topic')} -> {first_line}")

                    prompt = build_prompt(lang, past_topics, recent_snippets)
                    continue

                # attach language id and persist
                content["language"] = lang_id
                try:
                    entry_id = db.add_history(content)
                except Exception:
                    entry_id = None
                content["db_id"] = entry_id
                # Honor lightweight flag for AI generation to allow faster test renders
                try:
                    ai_lightweight = os.getenv('AI_LIGHTWEIGHT', 'false').lower() in ('1', 'true', 'yes')
                except Exception:
                    ai_lightweight = False
                content['lightweight'] = ai_lightweight
                return content

            except Exception as e:
                print(f"Error generating content on attempt {attempt}: {e}")
                continue

        print("AI generation exhausted attempts. Returning None.")
        return None

    def _get_mock_content(self):
        return {
            "topic": "Array Reduce",
            "question": "Write a function to sum an array using reduce()",
            "code": "const nums = [1, 2, 3, 4];\n\nconst sum = nums.reduce((acc, curr) => {\n  return acc + curr;\n}, 0);\n\nconsole.log(sum);",
            "title": "Master Array Reduce in 10 Seconds! 🚀 #shorts #javascript",
            "description": "Learn how to use the reduce method in JavaScript. #shorts #webdev #coding",
            "tags": ["javascript", "coding", "webdev"],
            "language": "javascript",
        }

