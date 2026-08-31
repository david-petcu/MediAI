import streamlit as st

st.set_page_config(page_title="MediAI Dashboard", layout="wide")

if 'logged_in_user' not in st.session_state:
    st.session_state.logged_in_user = None
if 'auth_access_token' not in st.session_state:
    st.session_state.auth_access_token = None
if 'auth_refresh_token' not in st.session_state:
    st.session_state.auth_refresh_token = None
if 'selected_doctor' not in st.session_state:
    st.session_state.selected_doctor = None

# Send all users to the main search page.
st.switch_page("pages/1_Search.py")
