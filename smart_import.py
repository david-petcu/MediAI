import argparse
import os
import pandas as pd
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from database import get_admin_client
from seed_database import USERS_DATA
from groq import Groq
from dotenv import load_dotenv

# 1. LOAD ENVIRONMENT VARIABLES
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY cannot be found in the .env file!")

client = Groq(api_key=GROQ_API_KEY)
supabase = get_admin_client()

TARGET_TOTAL_REVIEWS = 300
DEFAULT_DATASET_PATH = (
    Path(__file__).resolve().parent
    / "2021_german_doctor_reviews.csv"
    / "2021_german_doctor_reviews.csv"
)


# 2. HELPER FUNCTIONS
def clean_basic_html(text):
    if pd.isna(text): return ""
    text = str(text)
    # Remove any HTML tags (e.g., <br />, <strong>)
    text = re.sub(r'<[^>]+>', ' ', text)
    return text.strip()


def get_db_data():
    """Fetches specialties, doctors, and seeded user IDs from Supabase."""
    spec_res = supabase.table("specialties").select("id, name").execute()
    specialties = spec_res.data if spec_res.data else []

    doc_res = supabase.table("doctors").select("id, specialty_id").execute()
    doctors = doc_res.data if doc_res.data else []

    seed_user_emails = [user["email"] for user in USERS_DATA]
    user_res = supabase.table("users").select("id, email").in_("email", seed_user_emails).execute()
    users_by_email = {user["email"]: user["id"] for user in user_res.data} if user_res.data else {}
    user_ids = [users_by_email[email] for email in seed_user_emails if email in users_by_email]

    doc_by_spec = {}
    spec_names = []

    for s in specialties:
        spec_names.append(s['name'])
        doc_by_spec[s['name']] = [d['id'] for d in doctors if d['specialty_id'] == s['id']]

    all_doctors = [d['id'] for d in doctors]
    return spec_names, doc_by_spec, all_doctors, user_ids


# 3. AI PROCESSING (GPT OSS 120B)
def analyze_and_translate_review(german_text, specialty_list):
    prompt = f'''
    You are an AI data processor with a critical task: translate and completely anonymize a German patient review.

    **Your instructions are absolute. Follow them precisely.**

    **Step 1: Translate**
    Translate the German text into clear, natural English.

    **Step 2: Anonymize (Most Important Step!)**
    You MUST remove all personal and specific names. This includes:
    - Doctor names (e.g., "Dr. Schmidt", "Dr. Wicke-Wittenius", "Dr. Büchl")
    - Patient names (e.g., "Herr Müller")
    - Clinic or practice names.
    - Names of review websites (e.g., "Jameda").

    Replace them strictly with generic terms:
    - "Dr. [Name]" or any doctor name becomes "the doctor".
    - "Herr/Frau [Name]" becomes "the patient".
    - Any team member name becomes "a staff member" or "the nurse".
    - A practice or hospital name becomes "the practice" or "the clinic".

    **Anonymization Examples:**
    - GERMAN: "Dr. Büchl hat mein Überbein hervoragend operiert."
      - WRONG ENGLISH: "Dr. Büchl excellently operated on my ganglion."
      - CORRECT ENGLISH: "The doctor excellently operated on my ganglion."
    - GERMAN: "Ich war bei Dr. Wicke-Wittenius und das Team war super."
      - WRONG ENGLISH: "I was at Dr. Wicke-Wittenius and the team was great."
      - CORRECT ENGLISH: "I was at the clinic and the team was great."

    **Step 3: Categorize**
    Identify the most likely medical specialty from the context. Choose ONLY from this list: {specialty_list}.
    
    CRITICAL RULES FOR "Unknown":
    - If the review is generic (e.g., "Great doctor", "Waited too long", "Friendly staff") -> YOU MUST CHOOSE "Unknown".
    - If the review mentions a routine checkup or consultation BUT DOES NOT mention a specific disease or body part -> YOU MUST CHOOSE "Unknown".
    
    CRITICAL RULES FOR SPECIALTIES:
    - "Gastroenterology" -> CHOOSE THIS ONLY IF stomach, digestion, intestines, or abdominal issues are explicitly mentioned.
    - "Dentistry" -> CHOOSE THIS ONLY IF teeth, jaw, gums, or dentist are explicitly mentioned.
    - "General Surgery" -> CHOOSE THIS ONLY IF an operation, surgery, or cutting is explicitly mentioned.
    
    **Step 4: STRICT ANONYMIZATION CHECK & Format Output**
    Before generating the JSON, verify that the translated text contains ZERO names. 
    FATAL ERROR TRIGGER: If the words "Dr.", "Herr", "Frau", or any specific last name (e.g., "Rüssmann", "Schmidt") appear in your final English text, you have failed.
    Always use "the doctor", "the staff", or "the clinic".
    Return ONLY a valid JSON object. Do not add any other text, markdown formatting, or explanations.

    **German Text to Process:**
    "{german_text}"

    **JSON Output Format:**
    {{
        "translated_text": "The perfectly anonymized english translation...",
        "specialty": "Chosen Specialty or Unknown"
    }}
    '''

    retry_delays = [5, 10, 20]

    for attempt in range(len(retry_delays) + 1):
        try:
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-120b",
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            result_json = json.loads(response.choices[0].message.content)
            return result_json['translated_text'], result_json['specialty']
        except Exception as e:
            if attempt < len(retry_delays):
                wait_time = retry_delays[attempt]
                print(f"  [AI Warning]: {e}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            print(f"  [AI Error]: {e}")
            return None, None


# 4. MAIN EXECUTION
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import demonstration reviews into MediAI.")
    parser.add_argument(
        "--dataset",
        default=os.getenv("REVIEW_DATASET_PATH", str(DEFAULT_DATASET_PATH)),
        help="Path to the source CSV file.",
    )
    args = parser.parse_args()
    file_name = Path(args.dataset).expanduser().resolve()

    if not file_name.is_file():
        raise FileNotFoundError(
            f"Dataset not found: {file_name}. Set REVIEW_DATASET_PATH or use --dataset."
        )

    print("Fetching doctors, specialties, and users from the database...")
    spec_names, doc_by_spec, all_doctors, user_ids = get_db_data()

    if not all_doctors or not user_ids:
        print("Error: Missing doctors or users in the database! Run seed_database.py first.")
        exit()

    try:
        df = pd.read_csv(file_name)
        df = df.dropna(subset=['comment'])
        df['word_count'] = df['comment'].apply(lambda x: len(str(x).split()))
        df_valid = df[df['word_count'] >= 4].copy()

        # Apply the HTML cleaning
        df_valid['clean_comment'] = df_valid['comment'].apply(clean_basic_html)

        test_reviews = df_valid

        print(f"\nStarting AI Processing until {TARGET_TOTAL_REVIEWS} reviews are imported...\n")

        TARGET_RPM = 4.0
        INTERVAL_SECONDS = 60.0 / TARGET_RPM

        # --- SMART LOAD BALANCER ---
        # Keep track of how many reviews each doctor has received during this import session.
        doc_review_counts = {doc_id: 0 for doc_id in all_doctors}
        used_review_days = set()
        base_review_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
        inserted_count = 0

        for index, row in test_reviews.iterrows():
            if inserted_count >= TARGET_TOTAL_REVIEWS:
                break

            cycle_start_time = time.time()

            original_text = row['clean_comment']
            original_stars = row.get('rating', 1)
            if pd.isna(original_stars): original_stars = 1

            adapted_stars = max(1, min(5, 6 - int(original_stars)))

            print(f"[{index}] Processing review...")

            translated_text, chosen_specialty = analyze_and_translate_review(original_text, spec_names)

            if not translated_text:
                continue

            # --- PYTHON SAFETY NET (Regex Catcher) ---
            # This line looks for any "Dr. [Name]" that has escaped the AI and forces it into "the doctor"
            translated_text = re.sub(r'\bDr\.\s*[A-Z][a-zäöüß]+', 'the doctor', translated_text)
            translated_text = re.sub(r'\bDr\s+[A-Z][a-zäöüß]+', 'the doctor', translated_text)

            # --- BALANCED ASSIGNMENT LOGIC ---
            if chosen_specialty in doc_by_spec:
                available_doctors = doc_by_spec[chosen_specialty]
                if available_doctors:
                    # Pick the doctor in this specialty who has the LEAST reviews so far
                    assigned_doc_id = min(available_doctors, key=lambda d: doc_review_counts[d])
                    assignment_type = f"PRECISE ({chosen_specialty})"
                else:
                    continue
            elif chosen_specialty == "Unknown":
                # For generic reviews, pick the doctor across the ENTIRE DB who has the LEAST reviews
                assigned_doc_id = min(all_doctors, key=lambda d: doc_review_counts[d])
                assignment_type = "BALANCED (Filling Gaps)"
            else:
                continue

            # --- DATABASE INSERTION ---
            try:
                assigned_user_id = user_ids[inserted_count % len(user_ids)]
                review_date_offset = inserted_count // len(user_ids)
                created_at = base_review_date + timedelta(days=review_date_offset)

                while (assigned_user_id, assigned_doc_id, created_at.date()) in used_review_days:
                    review_date_offset += 1
                    created_at = base_review_date + timedelta(days=review_date_offset)

                used_review_days.add((assigned_user_id, assigned_doc_id, created_at.date()))

                res = supabase.table("reviews").insert({
                    "doctor_id": assigned_doc_id,
                    "user_id": assigned_user_id,
                    "stars": adapted_stars,
                    "review_text": translated_text,
                    "created_at": created_at.isoformat()
                }).execute()

                # Increment the review count for this specific doctor
                doc_review_counts[assigned_doc_id] += 1
                inserted_count += 1

                print(f"  [SUCCESS] Assigned: {assignment_type} | Stars: {adapted_stars}")
                print(f"  [TEXT]: {translated_text}\n")
                print("-" * 50)

            except Exception as db_err:
                print(f"  [ERROR] Database Insert failed: {db_err}")

            elapsed_time = time.time() - cycle_start_time
            time_to_sleep = INTERVAL_SECONDS - elapsed_time
            if time_to_sleep > 0: time.sleep(time_to_sleep)

    except Exception as e:
        print(f"General Execution Error: {e}")
