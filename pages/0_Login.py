import streamlit as st
from auth_session import store_auth_session
from database import create_public_client
from sidebar import render_sidebar

st.set_page_config(page_title="Login - MediAI", layout="centered")

render_sidebar()

st.markdown("""
    <style>
        div[data-testid="stForm"] {
            border-radius: 8px;
        }
        div[data-testid="stFormSubmitButton"] button {
            min-height: 46px;
            font-weight: 700;
        }
    </style>
""", unsafe_allow_html=True)

st.title("MediAI")
st.caption("Smart Healthcare Platform")
st.subheader("Access your account")

tab_login, tab_register = st.tabs(["Login", "Sign Up"])

with tab_login:
    with st.form("login_form"):
        email = st.text_input("Email address")
        password = st.text_input("Password", type="password")
        submit_btn = st.form_submit_button("Login", use_container_width=True)

        if submit_btn:
            email = email.strip().lower()
            if not email or not password:
                st.error("Please fill all fields.")
            else:
                try:
                    client = create_public_client()
                    auth_response = client.auth.sign_in_with_password({
                        "email": email,
                        "password": password,
                    })
                    store_auth_session(auth_response)
                    st.success("Login successful.")
                    st.switch_page("pages/1_Search.py")
                except Exception:
                    st.error("Invalid email or password.")

with tab_register:
    with st.form("register_form"):
        new_user = st.text_input("Full name")
        new_email = st.text_input("Email address")
        new_password = st.text_input("Password", type="password")
        reg_btn = st.form_submit_button("Create Account", use_container_width=True)

        if reg_btn:
            new_user = new_user.strip()
            new_email = new_email.strip().lower()
            if not new_user or not new_email or not new_password:
                st.error("Please fill all fields.")
            elif len(new_password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                try:
                    client = create_public_client()
                    auth_response = client.auth.sign_up({
                        "email": new_email,
                        "password": new_password,
                        "options": {
                            "data": {"username": new_user}
                        },
                    })

                    if auth_response.session:
                        store_auth_session(auth_response)
                        st.success("Account created successfully.")
                        st.switch_page("pages/1_Search.py")
                    else:
                        st.success("Account created. Check your email to confirm the account before logging in.")
                except Exception:
                    st.error("This email address or name is already registered.")
