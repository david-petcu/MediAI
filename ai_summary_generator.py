from database import get_admin_client
from ai_engine import generate_doctor_summary
import time

supabase = get_admin_client()

def generate_summaries_for_all_doctors():
    print("\n[SYSTEM] Starting aggregated summary generation for all doctors...\n")

    response = supabase.table("doctors").select("id, full_name").execute()
    doctors = response.data

    if not doctors:
        print("[INFO] No doctors found in the database.")
        return

    for doc in doctors:
        doc_id = doc['id']
        doc_name = doc['full_name']
        print(f"[PROCESS] Evaluating: {doc_name}...")

        rev_response = supabase.table("reviews").select("stars, review_text").eq("doctor_id", doc_id).order("created_at", desc=True).execute()
        reviews = rev_response.data or []

        if not reviews:
            print("  [SKIP] No reviews found. Skipping.\n")
            continue

        review_count = len(reviews)
        total_stars = sum([r['stars'] for r in reviews])
        average_rating = round(total_stars / review_count, 2)

        # Limited to the latest 20 reviews, matching the live AI worker
        reviews_to_summarize = reviews[:20]
        text_list = [r['review_text'] for r in reviews_to_summarize]

        print(f"  [INFO] Generating summary from {len(reviews_to_summarize)} reviews (out of {review_count} total)...")

        try:
            ai_summary = generate_doctor_summary(text_list)

            print(f"  [RESULT] Average Rating: {average_rating} | Count: {review_count}")
            print(f"  [SUMMARY]: {ai_summary}")

            supabase.table("reviews_summary").upsert({
                "doctor_id": doc_id,
                "average_rating": average_rating,
                "review_count": review_count,
                "summary": ai_summary
            }).execute()

            print("  [SUCCESS] Doctor profile updated successfully!")

        except Exception as e:
            print(f"  [ERROR] Failed to generate/save summary for {doc_name}: {e}")

        # 12 seconds break for safety
        print("  [WAIT] Pausing for 12 seconds to respect Groq Token Limits...\n")
        time.sleep(12)

    print("\n[SUCCESS] All summaries have been generated and saved!")


if __name__ == "__main__":
    generate_summaries_for_all_doctors()
