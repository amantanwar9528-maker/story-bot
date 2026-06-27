"""
Story script generation using the Gemini API — fully in Hindi.
The AI generates unique topics automatically, checking against
previously published stories to never repeat.

Uses gemini-2.5-flash-lite (highest free tier: 1000 RPD, 30 RPM).
Includes retry logic with exponential backoff for rate limiting.
"""
import json
import random
import logging
import time

import requests
import google.generativeai as genai

from config import (
    GEMINI_API_KEY, TARGET_WORD_COUNT, STORY_LANGUAGE_NAME,
    GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL,
)
from utils import logger, extract_json_from_response, validate_content_safety

genai.configure(api_key=GEMINI_API_KEY)


class ScriptWriter:
    """Generates AI-created Hindi story scripts via Gemini API."""

    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        self.model = genai.GenerativeModel(model_name)
        self.generation_config = genai.GenerationConfig(
            temperature=0.9,
            top_p=0.95,
            max_output_tokens=8192,
        )
        self.max_retries = 5

    def _generate_with_retry(self, prompt: str) -> str:
        """
        Generate text using Gemini, with an automatic free Groq fallback.

        Gemini is tried first. If it is rate-limited (429 /
        RESOURCE_EXHAUSTED), we do NOT sit and wait — we switch straight
        to Groq so the pipeline never stalls. Only transient overloads
        (503) get a short retry on Gemini.
        """
        last_error = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=self.generation_config,
                )
                return response.text

            except Exception as e:
                error_str = str(e)
                last_error = e

                # Rate limit / quota exhausted → go straight to Groq
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    logger.warning(
                        "  Gemini rate-limited/quota exhausted — "
                        "switching to free Groq fallback (no wait)"
                    )
                    break

                # Temporary overload → short retry, then fall back
                elif "503" in error_str or "UNAVAILABLE" in error_str:
                    wait_time = 5 * attempt
                    logger.warning(
                        f"  Gemini overloaded (attempt {attempt}/{self.max_retries}), "
                        f"waiting {wait_time}s..."
                    )
                    time.sleep(wait_time)
                    continue

                # Any other error → try Groq instead of crashing
                else:
                    logger.error(f"  Gemini API error: {error_str[:300]}")
                    break

        # ── Fallback: free Groq LLM ──
        groq_text = self._generate_with_groq(prompt)
        if groq_text:
            return groq_text

        raise RuntimeError(
            f"Both Gemini and Groq failed. Last Gemini error: {last_error}"
        )

    def _generate_with_groq(self, prompt: str) -> str:
        """
        Free fallback: generate text via Groq (OpenAI-compatible API).
        Returns the response text, or "" if unavailable.
        """
        if not GROQ_API_KEY:
            logger.error("  GROQ_API_KEY not set — no fallback available")
            return ""

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "तुम एक उस्ताद कहानीकार (master storyteller) हो जो "
                        "केवल valid JSON में जवाब देता है, कोई extra text नहीं।"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "top_p": 0.95,
            "max_tokens": 8192,
        }

        for attempt in range(1, 4):
            try:
                logger.info(
                    f"  Groq fallback request "
                    f"(model={GROQ_MODEL}, attempt {attempt}/3)"
                )
                r = requests.post(
                    GROQ_BASE_URL, headers=headers, json=payload, timeout=180
                )
                if r.status_code == 200:
                    data = r.json()
                    return data["choices"][0]["message"]["content"]
                elif r.status_code == 429:
                    wait = 20 * attempt
                    logger.warning(f"  Groq rate-limited, waiting {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    logger.error(f"  Groq error {r.status_code}: {r.text[:200]}")
                    time.sleep(5)
            except requests.RequestException as e:
                logger.warning(f"  Groq request failed (attempt {attempt}): {e}")
                time.sleep(5)

        logger.error("  Groq fallback exhausted")
        return ""

    # ── AI Topic Generation ─────────────────────────────────
    def generate_unique_topics(
        self,
        used_topics: list[str],
        count: int = 3,
        topic_type: str = "children",
    ) -> list[dict]:
        """
        Ask Gemini to generate unique story topics in Hindi that
        haven't been used before.
        """
        if topic_type == "children":
            genre_desc = (
                "बच्चों की कहानी (children's story) — रोमांचक, "
                "जादुई, शैक्षिक, और नैतिक मूल्यों से भरपूर"
            )
        else:
            genre_desc = (
                "डरावनी कहानी (horror story) — रहस्यमय, "
                "सस्पेंस से भरपूर, पर बच्चों के लिए उपयुक्त "
                "(कोई अत्यधिक हिंसा या खून नहीं)"
            )

        used_list = "\n".join(f"  - {t}" for t in used_topics[-50:]) if used_topics else "  (कोई पिछली कहानी नहीं)"

        prompt = f"""तुम एक रचनात्मक कहानी लेखक हो। हिंदी में {count} नई, अद्वितीय 
{genre_desc} विषय (topics) बनाओ।

नियम:
1. नीचे दी गई पहले से उपयोग की गई कहानियों की सूची में से कोई भी विषय दोहराओ मत।
2. हर विषय एक दूसरे से बिल्कुल अलग होना चाहिए — अलग पात्र, अलग स्थान, अलग कथानक।
3. विषय का शीर्षक (title) आकर्षक और छोटा हो (अधिकतम 60 अक्षर)।
4. विषय का विवरण (description) 2-3 वाक्यों में हो, जिससे कहानी की रूपरेखा समझ आ जाए।
5. सब कुछ हिंदी (देवनागरी लिपि) में हो।

पहले से उपयोग की गई कहानियाँ:
{used_list}

केवल valid JSON इस format में दो, कोई अन्य text नहीं:
{{
  "topics": [
    {{
      "title": "हिंदी में कहानी का शीर्षक",
      "description": "हिंदी में 2-3 वाक्यों का विवरण"
    }}
  ]
}}"""

        logger.info(f"Gemini से {count} Hindi topics बनवाए जा रहे हैं...")

        response_text = self._generate_with_retry(prompt)
        data = extract_json_from_response(response_text)

        if data and "topics" in data:
            topics = data["topics"]
            unique = [
                t for t in topics
                if t.get("title", "") not in used_topics
            ]
            if len(unique) < count:
                logger.warning(
                    f"Gemini repeated {count - len(unique)} topics, "
                    f"using available {len(unique)}"
                )
            logger.info(f"Gemini generated {len(unique)} unique Hindi topics")
            return unique[:count]

        logger.error("Failed to parse AI-generated topics")
        return []

    # ── Script Generation ──────────────────────────────────
    def _build_prompt(self, topic_title: str, topic_desc: str, topic_type: str) -> str:
        """Construct the Hindi prompt for Gemini."""

        if topic_type == "children":
            style_guide = (
                "बच्चों के लिए लिखो (उम्र 5-12 साल)। आसान हिंदी शब्दों का उपयोग करो, "
                "जीवंत वर्णनों के साथ, और हर कहानी में कोई नैतिक शिक्षा (moral lesson) हो। "
                "कहानी में रोमांच, जादू, और मज़ा होना चाहिए।"
            )
        else:
            style_guide = (
                "डरावनी लेकिन उम्र-उपयुक्त (age-appropriate) कहानी लिखो। "
                "रहस्य और सस्पेंस बनाओ, विस्तृत ध्वनि-वर्णन के साथ। "
                "कोई ग्राफिक हिंसा, खून, या अश्लीलता नहीं।"
            )

        return f"""तुम एक उस्ताद कहानीकार (master storyteller) हो। 
"{topic_title}" विषय पर एक पूरी {topic_type} कहानी हिंदी में लिखो।

कहानी का विवरण: {topic_desc}

{style_guide}

कहानी लगभग 40-45 मिनट की सुनी जा सके (लगभग {TARGET_WORD_COUNT} शब्द)। 
कहानी को 40-60 दृश्यों (scenes) में तोड़ो, हर दृश्य लगभग 45-75 सेकंड का।

हर दृश्य के लिए ये दो:
1. "narration": कथक (narrator) द्वारा बोला जाने वाला सटीक हिंदी टेक्स्ट (2-4 वाक्य)। 
   भावनाओं को शब्दों से व्यक्त करो ताकि आवाज़ में भावना झलके।
2. "visual_prompt": इस दृश्य के लिए cartoon-style illustration बनाने हेतु 
   विस्तृत prompt (अंग्रेजी में, क्योंकि image AI अंग्रेजी समझता है)। 
   हर prompt इस तरह शुरू करो: "cartoon style, children's book illustration, 
   vibrant colors, "। फिर पात्रों, स्थान, क्रिया, और मूड का वर्णन करो।
3. "mood": एक शब्द: happy, sad, excited, mysterious, scary, peaceful, या tense

ये भी दो:
- "title": YouTube के लिए आकर्षक शीर्षक (हिंदी में, अधिकतम 70 अक्षर)
- "description": YouTube विवरण (हिंदी में, 2-3 पैराग्राफ, एक hook के साथ)
- "tags": 10-15 YouTube SEO tags (हिंदी और अंग्रेजी मिश्रित)

केवल valid JSON इस structure में:
{{
  "title": "...",
  "description": "...",
  "tags": ["tag1", "tag2"],
  "scenes": [
    {{
      "narration": "हिंदी में कथन",
      "visual_prompt": "English prompt for image AI",
      "mood": "happy"
    }}
  ]
}}

JSON के पहले या बाद में कोई और text नहीं।"""

    def generate_script(
        self,
        topic: dict,
        topic_type: str = "children",
    ) -> dict:
        """
        Generate a complete Hindi story script from an AI-created topic.
        """
        topic_title = topic.get("title", "")
        topic_desc = topic.get("description", "")

        logger.info(f"हिंदी स्क्रिप्ट बन रही है: '{topic_title}' ({topic_type})")

        prompt = self._build_prompt(topic_title, topic_desc, topic_type)

        response_text = self._generate_with_retry(prompt)
        script_data = extract_json_from_response(response_text)

        if script_data is None:
            logger.error("स्क्रिप्ट JSON पार्स नहीं हुआ। दोबारा कोशिश...")
            retry_text = self._generate_with_retry(
                "केवल valid JSON दो, कोई markdown नहीं। " + prompt
            )
            script_data = extract_json_from_response(retry_text)

        if script_data is None:
            raise RuntimeError("स्क्रिप्ट बनाने में विफल")

        if not validate_content_safety(script_data):
            raise ValueError("जनित सामग्री सुरक्षा जांच में विफल")

        scene_count = len(script_data.get("scenes", []))
        total_words = sum(
            len(s.get("narration", "").split())
            for s in script_data.get("scenes", [])
        )
        est_minutes = total_words / 120

        logger.info(
            f"स्क्रिप्ट तैयार: '{script_data.get('title')}' | "
            f"{scene_count} दृश्य | {total_words} शब्द | ~{est_minutes:.0f} मिनट"
        )

        if est_minutes > 50:
            logger.warning(
                f"अनुमानित अवधि {est_minutes:.0f} मिनट — 45 मिनट से अधिक!"
            )

        script_data["topic"] = topic_title
        script_data["topic_description"] = topic_desc
        script_data["topic_type"] = topic_type
        return script_data
