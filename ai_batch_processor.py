from database import get_admin_client
from ai_engine import analyze_review_full, generate_doctor_summary
import time

supabase = get_admin_client()

def calculate_consistency(user_stars, ai_stars):
    difference = abs(user_stars - ai_stars)
    # The maximum difference is 4 (between 1 and 5 stars).
    # If the difference is 0, score is 1.0 (100% consistent)
    score = 1.0 - (difference / 4.0)
    return round(max(0.0, score), 2)  # Ensure score doesn't drop below 0 in edge cases

def update_doctor_summary(doctor_id):
    reviews_res = supabase.table("reviews").select("stars, review_text").eq("doctor_id", doctor_id).order("created_at", desc=True).execute()
    reviews = reviews_res.data or []

    review_count = len(reviews)
    average_rating = round(sum(r["stars"] for r in reviews) / review_count, 2) if review_count else 0.0
    recent_texts = [r["review_text"] for r in reviews[:20]]
    summary = generate_doctor_summary(recent_texts) if recent_texts else "No reviews available yet."

    supabase.table("reviews_summary").upsert({
        "doctor_id": doctor_id,
        "average_rating": average_rating,
        "review_count": review_count,
        "summary": summary
    }).execute()

def process_unlabeled_reviews(limit=10):
    print(f"\n[SYSTEM] Searching for up to {limit} unprocessed reviews...")

    # Fetching unprocessed reviews (where ai_tags is null)
    try:
        response = supabase.table("reviews").select("*").is_("ai_tags", "null").order("id").limit(limit).execute()
        reviews = response.data
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to fetch data from Supabase: {e}")
        return

    if not reviews:
        print("[INFO] No pending reviews found. System is fully updated.")
        return

    print(f"[INFO] Found {len(reviews)} reviews. Starting Groq AI Background Processing...\n")

    # --- OPTIMIZED RATE LIMITER SETTINGS ---
    TARGET_RPM = 14.0  # Safe margin below Groq's 30 RPM limit
    INTERVAL_SECONDS = 60.0 / TARGET_RPM

    processed_count = 0
    affected_doctor_ids = set()

    for rev in reviews:
        cycle_start_time = time.time()  # Start the stopwatch for this cycle

        rev_id = rev['id']
        text = rev['review_text']
        user_stars = rev['stars']

        print(f"[{processed_count + 1}/{len(reviews)}] Processing Review ID: {rev_id}...")

        try:
            # Single API call to the consolidated function
            tags, ai_stars = analyze_review_full(text)

            # Mathematical validation
            consistency = calculate_consistency(user_stars, ai_stars)

            print(f"   [RESULT] AI Stars: {ai_stars} | User Stars: {user_stars} | Trust Score: {consistency}")
            print(f"   [TAGS] Extracted: {tags}")

            # Database Update
            supabase.table("reviews").update({
                "ai_tags": tags,
                "consistency_score": consistency
            }).eq("id", rev_id).execute()

            processed_count += 1
            affected_doctor_ids.add(rev["doctor_id"])

        except Exception as e:
            print(f"   [ERROR] Failed to process review {rev_id}: {e}")
            print("   [INFO] Skipping to the next item...")

        # --- DYNAMIC SLEEP ---
        # Calculates exactly how much time is left in the 2.14 second window
        elapsed_time = time.time() - cycle_start_time
        time_to_sleep = INTERVAL_SECONDS - elapsed_time

        if time_to_sleep > 0:
            time.sleep(time_to_sleep)

    for doctor_id in affected_doctor_ids:
        print(f"[SUMMARY] Updating doctor summary for {doctor_id}...")
        update_doctor_summary(doctor_id)

    print(f"\n[SUCCESS] Batch processing complete. Successfully updated {processed_count} reviews.")


if __name__ == "__main__":
    # You can set the limit high (e.g., 500) because the dynamic rate limiter prevents crashes
    process_unlabeled_reviews(limit=500)
