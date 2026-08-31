import os
import random
from database import get_admin_client

supabase = get_admin_client()

# 1. STRUCTURED MOCK DATA
# Dictionary mapping exactly 10 specialties to 3 distinct English doctors each
DOCTORS_DATA = {
    "Cardiology": ["Dr. William Hart", "Dr. Eleanor Vance", "Dr. Arthur Pendelton"],
    "Dermatology": ["Dr. Sarah Jenkins", "Dr. Oliver Brooks", "Dr. Chloe Bennett"],
    "Neurology": ["Dr. James Sterling", "Dr. Margaret Hughes", "Dr. Thomas Clarke"],
    "Pediatrics": ["Dr. Emily Parker", "Dr. Benjamin Hayes", "Dr. Lucy Daniels"],
    "Orthopedics": ["Dr. Michael Stone", "Dr. Alice Morgan", "Dr. David Fisher"],
    "General Surgery": ["Dr. Richard Evans", "Dr. Laura Mitchell", "Dr. Daniel Harrison"],
    "Psychiatry": ["Dr. Robert Palmer", "Dr. Victoria Gibson", "Dr. Edward Norton"],
    "Ophthalmology": ["Dr. Samuel Green", "Dr. Evelyn Foster", "Dr. Marcus Webb"],
    "Dentistry": ["Dr. Anthony Walker", "Dr. Samantha Reed", "Dr. Christopher Bell"],
    "Gastroenterology": ["Dr. Anthony Brooks", "Dr. Melissa Dunn", "Dr. Lawrence Ward"]
}

USERS_DATA = [
    {"username": "James Wilson", "email": "james.wilson@medi-ai.com"},
    {"username": "Emily Carter", "email": "emily.carter@medi-ai.com"},
    {"username": "Michael Brooks", "email": "michael.brooks@medi-ai.com"},
    {"username": "Sarah Mitchell", "email": "sarah.mitchell@medi-ai.com"},
    {"username": "Daniel Foster", "email": "daniel.foster@medi-ai.com"},
    {"username": "Olivia Bennett", "email": "olivia.bennett@medi-ai.com"},
    {"username": "William Parker", "email": "william.parker@medi-ai.com"},
    {"username": "Grace Turner", "email": "grace.turner@medi-ai.com"},
    {"username": "Henry Collins", "email": "henry.collins@medi-ai.com"},
    {"username": "Chloe Morgan", "email": "chloe.morgan@medi-ai.com"},
    {"username": "David Reynolds", "email": "david.reynolds@medi-ai.com"},
]

def get_seed_password():
    password = os.getenv("SEED_USER_PASSWORD")
    if not password:
        raise ValueError("SEED_USER_PASSWORD cannot be found in the environment.")
    return password


# 2. SEEDING FUNCTIONS
def generate_users():
    print(f"\n[SYSTEM] Generating {len(USERS_DATA)} test users...")
    user_ids = []
    seed_password = get_seed_password()

    for user in USERS_DATA:
        username = user["username"]
        email = user["email"]

        try:
            auth_res = supabase.auth.admin.create_user({
                "email": email,
                "password": seed_password,
                "email_confirm": True,
                "user_metadata": {"username": username},
            })
            user_id = str(auth_res.user.id)
            supabase.table('users').upsert({
                "id": user_id,
                "username": username,
                "email": email,
            }).execute()
            user_ids.append(user_id)
            print(f"  + Added user: {username}")
        except Exception:
            print(f"  - Skipped user {username} (already exists). Fetching ID...")
            existing = supabase.table('users').select('id').eq('email', email).execute()
            if existing.data:
                user_ids.append(existing.data[0]['id'])

    return user_ids


def generate_specialties_and_doctors():
    print("\n[SYSTEM] Generating 10 specialties and doctors...")
    doctor_ids = []

    for spec_name, doctor_list in DOCTORS_DATA.items():
        spec_id = None
        try:
            res_spec = supabase.table('specialties').insert({"name": spec_name}).execute()
            spec_id = res_spec.data[0]['id']
            print(f"\n[FOLDER] Created specialty: {spec_name}")
        except Exception:
            res_spec = supabase.table('specialties').select('id').eq('name', spec_name).execute()
            if res_spec.data:
                spec_id = res_spec.data[0]['id']
                print(f"\n[FOLDER] Found existing specialty: {spec_name}")
            else:
                continue

        if spec_id:
            for doc_name in doctor_list:
                doc_stamp = f"{random.randint(100000, 999999)}"

                try:
                    res_doc = supabase.table('doctors').insert({
                        "full_name": doc_name,
                        "stamp": doc_stamp,
                        "specialty_id": spec_id
                    }).execute()

                    doc_id = res_doc.data[0]['id']
                    doctor_ids.append(doc_id)

                    # CRITICAL: Create an empty row in reviews_summary for this doctor
                    supabase.table('reviews_summary').insert({
                        "doctor_id": doc_id,
                        "average_rating": 0.0,
                        "review_count": 0,
                        "summary": "No AI summary generated yet."
                    }).execute()

                    print(f"    + Added {doc_name} (Stamp: {doc_stamp})")
                except Exception as e:
                    print(f"    - Error adding {doc_name}: {e}")

    return doctor_ids


# 3. SCRIPT EXECUTION
if __name__ == "__main__":
    print("Starting MediAI database seeding process (Users & Doctors only)...")

    # Run only the user and doctor generators.
    users = generate_users()
    doctors = generate_specialties_and_doctors()

    print("\nDatabase population completed successfully. Ready for CSV import!")
