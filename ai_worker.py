import time
import threading
from database import get_admin_client
from ai_engine import analyze_review_full, generate_doctor_summary


def process_single_review_pipeline(review_id, doctor_id, user_stars, text):
    """This code runs in the background without blocking the application."""
    print(f"\n[AI WORKER] Awakened! Processing new review (ID: {review_id})...")

    try:
        supabase = get_admin_client()

        # Analyze the review text.
        tags, ai_stars = analyze_review_full(text)

        # Calculate consistency.
        difference = abs(user_stars - ai_stars)
        consistency = round(1.0 - (difference / 4.0), 2)

        # Save AI results.
        supabase.table("reviews").update({
            "ai_tags": tags,
            "consistency_score": consistency
        }).eq("id", review_id).execute()

        print(f"[AI WORKER] Review analyzed! Consistency score is: {consistency}")
        print("[AI WORKER] Pausing for 2.5 seconds for API limit safety...")
        time.sleep(2.5)  # Reduced pause due to API optimization

        # --- PART 2: DOCTOR SUMMARY ---
        print(f"[AI WORKER] Generating new doctor summary...")

        # 1. Calculate new mathematical average (fetch all doctor reviews)
        all_revs_res = supabase.table("reviews").select("stars").eq("doctor_id", doctor_id).execute()
        all_reviews = all_revs_res.data

        total_count = len(all_reviews)
        avg_rating = round(sum([r['stars'] for r in all_reviews]) / total_count, 2) if total_count > 0 else 0

        # 2. Fetch texts (max last 20 to stay within Groq TPM limits)
        texts_res = supabase.table("reviews").select("review_text").eq("doctor_id", doctor_id).order("created_at", desc=True).limit(20).execute()
        text_list = [r['review_text'] for r in texts_res.data]

        # 3. Request new paragraph from AI
        ai_summary = generate_doctor_summary(text_list)

        # 4. Save to summary table
        supabase.table("reviews_summary").upsert({
            "doctor_id": doctor_id,
            "average_rating": avg_rating,
            "review_count": total_count,
            "summary": ai_summary
        }).execute()

        print("[AI WORKER] Everything processed successfully! Worker going back to sleep.\n")

    except Exception as e:
        print(f"[AI WORKER] Background error: {e}")


def start_background_processing(review_id, doctor_id, user_stars, text):
    """Starts a separate execution thread"""
    # daemon=True means if the user closes the app abruptly, this thread closes automatically
    thread = threading.Thread(
        target=process_single_review_pipeline,
        args=(review_id, doctor_id, user_stars, text),
        daemon=True
    )
    thread.start()

def regenerate_doctor_summary_pipeline(doctor_id):
    """Runs in background to regenerate the AI summary after a review is deleted."""
    print(f"\n[AI WORKER] Regenerating summary for doctor {doctor_id} after deletion...")
    try:
        supabase = get_admin_client()
        reviews_res = supabase.table("reviews").select("stars, review_text").eq("doctor_id", doctor_id).order("created_at", desc=True).execute()
        reviews = reviews_res.data or []
        review_count = len(reviews)
        average_rating = round(sum(r["stars"] for r in reviews) / review_count, 2) if review_count else 0.0
        text_list = [r['review_text'] for r in reviews[:20]]

        if text_list:
            ai_summary = generate_doctor_summary(text_list)
        else:
            ai_summary = "No reviews available yet."

        supabase.table("reviews_summary").upsert({
            "doctor_id": doctor_id,
            "average_rating": average_rating,
            "review_count": review_count,
            "summary": ai_summary
        }).execute()

        print("[AI WORKER] Doctor summary updated successfully!\n")
    except Exception as e:
        print(f"[AI WORKER] Background error updating summary: {e}")

def start_summary_update_background(doctor_id):
    """Starts the background thread for updating the summary."""
    thread = threading.Thread(
        target=regenerate_doctor_summary_pipeline,
        args=(doctor_id,),
        daemon=True
    )
    thread.start()
