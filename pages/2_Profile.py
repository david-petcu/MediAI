import streamlit as st
import json
from collections import Counter
from database import supabase
from sidebar import render_sidebar

st.set_page_config(page_title="Doctor Profile - MediAI", layout="wide")

# Protection against direct access
if st.session_state.get('selected_doctor') is None:
    st.switch_page("pages/1_Search.py")

doc = st.session_state.selected_doctor

render_sidebar()

AI_SCORE_HELP = "Based on rating, review consistency, and popularity."
PENDING_AI_TEXT = "AI analysis pending."

st.markdown("""
    <style>
        .profile-meta {
            color: #4b5563;
            margin: -0.25rem 0 1rem 0;
        }
        .profile-meta strong {
            color: #2563eb;
        }
    </style>
""", unsafe_allow_html=True)

# Navigation button
if st.button("Back to Search"):
    st.switch_page("pages/1_Search.py")

# FETCH DATA FROM DATABASE
@st.cache_data(ttl=60)
def get_doctor_reviews(doctor_id):
    res = supabase.table("reviews").select("*, users(username)").eq("doctor_id", doctor_id).order("created_at", desc=True).execute()
    return res.data or []

try:
    reviews = get_doctor_reviews(doc['id'])
except Exception:
    st.error("Could not load doctor reviews. Please check the database connection and try again.")
    st.stop()

# Fetch live statistics without cache so background AI updates are reflected quickly.
def get_realtime_stats(doctor_id):
    res = supabase.table("reviews_summary").select("*").eq("doctor_id", doctor_id).execute()
    return res.data[0] if res.data else {"average_rating": 0.0, "review_count": 0, "summary": PENDING_AI_TEXT}

def calculate_ai_recommendation_score(doctor_id):
    res = supabase.table("reviews").select("stars, consistency_score").eq("doctor_id", doctor_id).execute()
    doctor_reviews = res.data or []

    if not doctor_reviews:
        return 0.0

    total = len(doctor_reviews)
    avg_stars = sum(r['stars'] for r in doctor_reviews) / total
    stars_points = (avg_stars / 5.0) * 45.0

    avg_trust = sum(
        (r['consistency_score'] if r['consistency_score'] is not None else 0.5)
        for r in doctor_reviews
    ) / total
    trust_points = avg_trust * 45.0

    popularity_points = min(10.0, total * 2.0)

    return round(stars_points + trust_points + popularity_points, 1)

spec_name = doc.get('specialties', {}).get('name', 'General Practice')

# Statistics
try:
    stats = get_realtime_stats(doc['id'])
    ai_score = calculate_ai_recommendation_score(doc['id'])
except Exception:
    st.error("Could not load doctor statistics. Please check the database connection and try again.")
    st.stop()

# PROFILE HEADER
st.title(doc['full_name'])
st.markdown(
    f"<div class='profile-meta'><strong>{spec_name}</strong> | Stamp Code: {doc['stamp']}</div>",
    unsafe_allow_html=True
)

# Main metrics
col1, col2, col3 = st.columns(3)
with col1:
    st.metric(label="Patient Rating", value=f"{stats['average_rating']} / 5")
with col2:
    st.metric(label="Total Reviews", value=f"{stats['review_count']}")
with col3:
    st.metric(label="AI Recommendation Score", value=f"{ai_score:.1f}%", help=AI_SCORE_HELP)

st.divider()

# ARTIFICIAL INTELLIGENCE ANALYSIS
st.subheader("AI Summary")
with st.container(border=True):
    st.markdown(stats.get('summary') or PENDING_AI_TEXT)
    st.caption("This AI summary is generated from patient reviews and does not represent an official clinical evaluation.")

# Extract highlight tags.
all_tags_list = []
for rev in reviews:
    # Use only 4 or 5 star reviews.
    if rev.get('stars', 0) >= 4 and rev.get('ai_tags'):
        try:
            tags = rev['ai_tags'] if isinstance(rev['ai_tags'], list) else json.loads(rev['ai_tags'])
            all_tags_list.extend(tags)
        except Exception:
            pass

# Format valid tags and count them automatically.
valid_tags = [t.lower().strip().title() for t in all_tags_list if len(t.split()) <= 3 and "is not" not in t.lower() and t.lower().strip() != "general"]
tags_dict = Counter(valid_tags)

# Render Highlights UI based on the filtered tags
if tags_dict:
    st.markdown("#### Patient Highlights")
    # Counter sorts the most frequent tags with most_common().
    sorted_tags = tags_dict.most_common(3)

    tag_vibe_map = {
        "Professionalism": "Highly Professional",
        "Communication": "Excellent Communicator",
        "Cleanliness": "Modern, Clean Office",
        "Punctuality": "Punctual Appointments",
        "Waiting Time": "Efficient Appointment Time",
        "Wait": "Efficient Appointment Time",
        "Care": "Attentive Care",
        "Compassion": "Very Caring & Patient",
        "Empathy": "Understanding & Empathetic",
        "Thorough": "Thorough Examination",
        "Diagnosis": "Accurate Diagnosis",
        "Cost": "Fair Pricing",
        "Staff": "Helpful Staff",
        "Listening": "Attentive Listener",
        "Treatment": "Effective Treatment",
        "Office": "Well-Organized Office",
    }

    vibe_cols = st.columns(len(sorted_tags))
    for i, (tag_name, count) in enumerate(sorted_tags):
        highlight_text = tag_name
        for key, text in tag_vibe_map.items():
            if key in tag_name:
                highlight_text = text
                break
        vibe_cols[i].success(highlight_text)
else:
    # If the doctor only has bad reviews (or no reviews), show a neutral fallback
    st.markdown("#### Patient Highlights")
    st.info("This doctor currently does not have enough highly-rated reviews to display positive highlights.")

st.divider()

# REVIEWS LIST
st.subheader("Patient Reviews")

filter_val = st.selectbox("Filter by rating:", ["All", "5 Stars", "4 Stars", "3 Stars", "2 Stars", "1 Star"], label_visibility="collapsed")

filtered_reviews = reviews
if filter_val != "All":
    target_stars = int(filter_val[0])
    filtered_reviews = [r for r in reviews if r['stars'] == target_stars]

if not filtered_reviews:
    st.write(f"No {filter_val.lower()} reviews found.")
else:
    for rev in filtered_reviews:
        reviewer = rev.get('users', {}).get('username', 'Anonymous') if rev.get('users') else 'Anonymous'
        consistency = rev.get('consistency_score')

        is_suspicious = consistency is not None and consistency < 0.6

        with st.container(border=True):
            if is_suspicious:
                st.error("AI consistency warning: this review has been marked as potentially inconsistent.")

            review_header, rating_col = st.columns([5, 1])
            with review_header:
                st.markdown(f"**User: {reviewer}**")
            with rating_col:
                st.metric("Rating", f"{rev['stars']} / 5")

            st.write(rev['review_text'])

            if consistency is not None:
                prog_val = float(consistency)
                if prog_val > 1.0:
                    prog_val = prog_val / 100.0

                st.caption(f"AI Trust Score: {int(prog_val * 100)}%")
                st.progress(prog_val)
            else:
                st.caption("AI Trust Score: AI analysis pending.")
