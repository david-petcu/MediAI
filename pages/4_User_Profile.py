import streamlit as st
from sidebar import render_sidebar
from ai_worker import start_summary_update_background
from auth_session import get_authenticated_client

st.set_page_config(page_title="User Profile - MediAI", layout="wide")

render_sidebar()

if st.session_state.get('logged_in_user') is None:
    st.warning("Access Restricted: You must be logged in to view your profile.")
    st.page_link("pages/0_Login.py", label="Click here to Login or Register")
    st.stop()

auth_supabase = get_authenticated_client()
if auth_supabase is None:
    st.warning("Your session has expired. Please log in again.")
    st.page_link("pages/0_Login.py", label="Go to Login")
    st.stop()

user = st.session_state.logged_in_user

st.title("My Profile")
st.markdown(f"Welcome back, **{user['username']}**!")
if st.session_state.pop("review_deleted", False):
    st.success("Review deleted.")
st.divider()

with st.expander("Change Password"):
    with st.form("change_password_form"):
        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm new password", type="password")
        change_password = st.form_submit_button("Update Password", use_container_width=True)

        if change_password:
            if len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                try:
                    auth_supabase.auth.update_user({"password": new_password})
                    st.success("Password updated successfully.")
                except Exception:
                    st.error("Password update failed. Please log in again and retry.")

def delete_review(review_id, doctor_id):
    try:
        auth_supabase.table("reviews").delete().eq("id", review_id).eq("user_id", user["id"]).execute()

        start_summary_update_background(doctor_id)

        st.cache_data.clear()
        st.session_state.review_deleted = True
    except Exception as e:
        st.error(f"Failed to delete review and update stats: {e}")

st.subheader("My Reviews")

try:
    res = auth_supabase.table("reviews").select("*, doctors(full_name)").eq("user_id", user['id']).order("created_at", desc=True).execute()
    reviews = res.data or []
except Exception as e:
    st.error(f"Error fetching reviews: {e}")
    reviews = []

if not reviews:
    st.info("You haven't posted any reviews yet.")
else:
    for rev in reviews:
        doc_name = rev.get('doctors', {}).get('full_name', 'Unknown Doctor') if rev.get('doctors') else 'Unknown Doctor'
        consistency = rev.get('consistency_score')

        with st.container(border=True):
            col1, col2 = st.columns([5, 1])

            with col1:
                review_header, rating_col = st.columns([5, 1])
                with review_header:
                    st.markdown(f"**Doctor: {doc_name}**")
                with rating_col:
                    st.metric("Rating", f"{rev['stars']} / 5")
                st.write(rev['review_text'])

                if consistency is not None:
                    prog_val = float(consistency)
                    if prog_val > 1.0:
                        prog_val = prog_val / 100.0
                    st.caption(f"AI Trust Score: {int(prog_val * 100)}%")
                else:
                    st.caption("AI Trust Score: AI analysis pending.")

            with col2:
                with st.popover("Delete", use_container_width=True):
                    st.markdown("Are you sure you want to delete this review?")
                    st.button(
                        "Yes, delete", 
                        key=f"del_{rev['id']}", 
                        use_container_width=True,
                        type="primary",
                        on_click=delete_review,
                        args=(rev['id'], rev['doctor_id'])
                    )
