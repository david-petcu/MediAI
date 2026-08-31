import streamlit as st
from database import create_authenticated_client


def store_auth_session(auth_response):
    session = auth_response.session
    user = auth_response.user

    if session is None or user is None:
        raise ValueError("Supabase did not return an authenticated session.")

    username = (user.user_metadata or {}).get("username") or user.email or "User"
    st.session_state.logged_in_user = {
        "id": str(user.id),
        "username": username,
        "email": user.email,
    }
    st.session_state.auth_access_token = session.access_token
    st.session_state.auth_refresh_token = session.refresh_token


def get_authenticated_client():
    access_token = st.session_state.get("auth_access_token")
    refresh_token = st.session_state.get("auth_refresh_token")

    if not access_token or not refresh_token:
        clear_auth_session()
        return None

    try:
        client, session = create_authenticated_client(access_token, refresh_token)
        st.session_state.auth_access_token = session.access_token
        st.session_state.auth_refresh_token = session.refresh_token
        return client
    except Exception:
        clear_auth_session()
        return None


def clear_auth_session():
    st.session_state.logged_in_user = None
    st.session_state.auth_access_token = None
    st.session_state.auth_refresh_token = None
