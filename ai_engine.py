import json
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY can't be found in .env!")


def call_groq(prompt, model_name="openai/gpt-oss-20b", is_json=False):
    """
    Generic API calling function.
    Defaults to GPT OSS 20B if no model is specified.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # We use temperature 0.0 when we need strict data formats like JSON
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "You are a helpful medical assistant. Always be concise."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0 if is_json else 0.2
    }

    if is_json:
        payload["response_format"] = {"type": "json_object"}

    retry_delays = [5, 10, 20]

    for attempt in range(len(retry_delays) + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            data = response.json()
            if "choices" in data:
                return data["choices"][0]["message"]["content"].strip()

            if response.status_code == 429 and attempt < len(retry_delays):
                wait_time = retry_delays[attempt]
                print(f"[WARN] Groq rate limit reached. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            print(f"[ERROR] Groq API Error: {data}")
            return None
        except Exception as e:
            if attempt < len(retry_delays):
                wait_time = retry_delays[attempt]
                print(f"[WARN] Groq connection error: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            print(f"[ERROR] Groq Connection Error: {e}")
            return None


# 2. ANALYSIS FUNCTIONS (Consolidated NLP - Using GPT OSS 20B)

def analyze_review_full(review_text):
    """
    Consolidated function: Extracts both tags and predicts stars in a single API call.
    Runs on GPT OSS 20B and returns a JSON object.
    """
    prompt = f"""
    You are an expert medical data analyst. Read the following patient review.

    You have TWO tasks:
    TASK 1: Extract the 2 most relevant tags regarding the doctor's service (e.g., "Cost", "Waiting Time", "Professionalism", "Cleanliness"). If none apply, use "General".
    TASK 2: Predict the sentiment as a star rating from 1 to 5 (1 = Terrible, 2 = Poor, 3 = Average, 4 = Good, 5 = Excellent).

    Review: "{review_text}"

    You MUST return ONLY a valid JSON object in this exact format, with no other text:
    {{
        "tags": ["Tag1", "Tag2"],
        "stars": 5
    }}
    """

    result = call_groq(prompt, is_json=True)

    if result:
        # We clean up any Markdown formatting (```json ... ```) introduced by LLM
        cleaned_result = result.replace("```json", "").replace("```JSON", "").replace("```", "").strip()

        try:
            result_json = json.loads(cleaned_result)
            # Ensure we get a list of tags and format them nicely
            raw_tags = result_json.get('tags', ['General'])
            if not isinstance(raw_tags, list):
                raw_tags = ['General']

            tags = [str(tag).strip().title() for tag in raw_tags][:2]

            # Ensure stars is an integer between 1 and 5
            stars = int(result_json.get('stars', 3))
            stars = max(1, min(5, stars))

            return tags, stars
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON Parsing Error in analyze_review_full: {e}")
            return ["General"], 3
        except ValueError as e:
            print(f"[ERROR] Value Parsing Error in analyze_review_full: {e}")
            return ["General"], 3

    # Fallback values if API call completely fails
    return ["General"], 3


# 3. COMPLEX SUMMARY FUNCTION (Text Generation)

def generate_doctor_summary(reviews_list):
    """Creates a professional summary from multiple reviews. (Runs on GPT OSS 120B)"""
    if not reviews_list:
        return "No reviews available for summary."

    text_blob = "\n- ".join(reviews_list)
    prompt = (
        "Write a concise 3-sentence summary of the following patient reviews "
        "for a doctor. Focus on medical quality and patient experience.\n"
        "IMPORTANT: Return ONLY the 3 sentences of the summary. "
        "Do NOT include any introductory phrases, conversational filler, or labels like 'Here is the summary'. "
        "Start directly with the first word of the summary.\n\n"
        f"Reviews:\n- {text_blob}"
    )

    # Use a stronger model for aggregated summaries.
    return call_groq(prompt, model_name="openai/gpt-oss-120b") or "Summary generation failed."
