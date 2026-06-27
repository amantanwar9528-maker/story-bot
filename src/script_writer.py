"""
Story script generation using the Gemini API — fully in Hindi.
The AI generates unique topics automatically, checking against
previously published stories to never repeat.

Pipeline:
  1. generate_unique_topics() — asks Gemini for fresh Hindi topics
  2. generate_script() — writes the full Hindi story with scenes
"""
import json
import random
import logging

import google.generativeai as genai

from config import GEMINI_API_KEY, TARGET_WORD_COUNT, STORY_LANGUAGE_NAME
from utils import logger, extract_json_from_response, validate_content_safety

genai.configure(api_key=GEMINI_API_KEY)


class ScriptWriter:
    """Generates AI-created Hindi story scripts via Gemini API."""

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model = genai.GenerativeModel(model_name)
        self.generation_config = genai.GenerationConfig(
            temperature=0.9,
            top_p=0.95,
            max_output_tokens=8192,
        )

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

        Args:
            used_topics: List of topic titles already published
            count: Number of new topics to generate
            topic_type: "children" or "horror"

        Returns:
            List of dicts with 'title' and 'description' in Hindi
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

        # Build the "already used" list for Gemini to avoid
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

        response = self.model.generate_content(
            prompt,
            generation_config=self.generation_config,
        )

        data = extract_json_from_response(response.text)

        if data and "topics" in data:
            topics = data["topics"]
            # Double-check none duplicate the used list
            unique = [
                t for t in topics
                if t.get("title", "") not in used_topics
            ]
            # If Gemini accidentally repeated some, generate more
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
        Args:
            topic: dict with 'title' and 'description' (in Hindi)
            topic_type: "children" or "horror"
        """
        topic_title = topic.get("title", "")
        topic_desc = topic.get("description", "")

        logger.info(f"हिंदी स्क्रिप्ट बन रही है: '{topic_title}' ({topic_type})")

        prompt = self._build_prompt(topic_title, topic_desc, topic_type)
        response = self.model.generate_content(
            prompt,
            generation_config=self.generation_config,
        )

        script_data = extract_json_from_response(response.text)

        if script_data is None:
            logger.error("स्क्रिप्ट JSON पार्स नहीं हुआ। दोबारा कोशिश...")
            retry = self.model.generate_content(
                "केवल valid JSON दो, कोई markdown नहीं। " + prompt,
                generation_config=self.generation_config,
            )
            script_data = extract_json_from_response(retry.text)

        if script_data is None:
            raise RuntimeError("स्क्रिप्ट बनाने में विफल")

        if not validate_content_safety(script_data):
            raise ValueError("जनित सामग्री सुरक्षा जांच में विफल")

        scene_count = len(script_data.get("scenes", []))
        total_words = sum(
            len(s.get("narration", "").split())
            for s in script_data.get("scenes", [])
        )
        est_minutes = total_words / 120  # Hindi WPM

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
