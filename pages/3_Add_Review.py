import streamlit as st
from datetime import datetime, time, timedelta, timezone
from database import supabase
from ai_worker import start_background_processing
from auth_session import get_authenticated_client
from sidebar import render_sidebar

st.set_page_config(page_title="Add Review - MediAI", layout="wide")

render_sidebar()

st.title("Write a Review")

# Access protection
if st.session_state.get('logged_in_user') is None:
    st.warning("Access Restricted: You must be logged in to share your experience.")
    st.page_link("pages/0_Login.py", label="Click here to Login or Register")
    st.stop()

auth_supabase = get_authenticated_client()
if auth_supabase is None:
    st.warning("Your session has expired. Please log in again.")
    st.page_link("pages/0_Login.py", label="Go to Login")
    st.stop()

st.markdown("Share your experience to help other patients make informed decisions.")

@st.cache_data(ttl=60)
def fetch_doctors():
    res = supabase.table("doctors").select("id, full_name").execute()
    return res.data if res.data else []

def has_reviewed_doctor_today(user_id, doctor_id):
    today = datetime.now(timezone.utc).date()
    start_of_day = datetime.combine(today, time.min, tzinfo=timezone.utc)
    next_day = start_of_day + timedelta(days=1)

    res = auth_supabase.table("reviews").select("id") \
        .eq("user_id", user_id) \
        .eq("doctor_id", doctor_id) \
        .gte("created_at", start_of_day.isoformat()) \
        .lt("created_at", next_day.isoformat()) \
        .limit(1) \
        .execute()

    return bool(res.data)

doctors_list = fetch_doctors()

if not doctors_list:
    st.info("No doctors are available for review yet.")
    st.stop()

doc_names = [d['full_name'] for d in doctors_list]

with st.form("add_review_form"):
    selected_doc_name = st.selectbox("Select a Doctor", doc_names)

    selected_stars = st.radio(
        "Rating",
        options=[1, 2, 3, 4, 5],
        index=4,
        format_func=lambda x: f"{x} Stars",
        horizontal=True
    )

    review_text = st.text_area("Review Content", height=150, help="Please provide details about your medical visit.")

    st.write("")
    submit_btn = st.form_submit_button("Submit Review", use_container_width=True)

    if submit_btn:
        if not review_text.strip():
            st.error("Please provide review text before submitting.")
        else:
            selected_doc_id = next((doc['id'] for doc in doctors_list if doc['full_name'] == selected_doc_name), None)

            if selected_doc_id:
                try:
                    if has_reviewed_doctor_today(st.session_state.logged_in_user['id'], selected_doc_id):
                        st.error("You have already reviewed this doctor today. Please try again another day.")
                    else:
                        # Save the review first.
                        res = auth_supabase.table("reviews").insert({
                            "doctor_id": selected_doc_id,
                            "user_id": st.session_state.logged_in_user['id'],
                            "stars": selected_stars,
                            "review_text": review_text
                        }).execute()

                        new_review_id = res.data[0]['id']

                        # Start background AI processing.
                        start_background_processing(new_review_id, selected_doc_id, selected_stars, review_text)

                        # Clear cached data so the new review appears immediately.
                        st.cache_data.clear()

                        st.success("Review submitted. AI analysis is in progress.")
                except Exception as e:
                    st.error("Submission failed. Please check your database connection or try again later.")
