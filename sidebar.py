import streamlit as st
from auth_session import clear_auth_session, get_authenticated_client

def render_sidebar():
    # CSS for controlling the Sidebar layout
    st.markdown("""
        <style>
            /* Hide automatic page list */
            [data-testid="stSidebarNav"] {display: none !important;}

            /* Adjust Sidebar width */
            [data-testid="stSidebar"] {
                min-width: 260px !important;
                max-width: 260px !important;
            }

            /* Navigation button style */
            section[data-testid="stSidebar"] .stButton button {
                height: 45px;
                font-size: 16px;
                font-weight: bold;
            }
        </style>
    """, unsafe_allow_html=True)

    with st.sidebar:
        st.title("MediAI")
        st.caption("Smart Healthcare Platform")

        st.write("")
        st.write("")

        # Main navigation without icons
        st.page_link("pages/1_Search.py", label="Search Doctors")
        st.write("")
        st.page_link("pages/3_Add_Review.py", label="Write a Review")

        st.write("")
        st.write("")
        st.divider()

        # Authentication / User Section
        if st.session_state.get('logged_in_user'):
            st.success(f"Logged in as:\n\n{st.session_state.logged_in_user['username']}")
            st.write("")
            st.page_link("pages/4_User_Profile.py", label="My Profile")
            st.write("")
            if st.button("Logout", use_container_width=True):
                client = get_authenticated_client()
                if client:
                    try:
                        client.auth.sign_out()
                    except Exception:
                        pass
                clear_auth_session()
                st.rerun()
        else:
            st.info("Welcome, Guest")
            st.write("")
            st.page_link("pages/0_Login.py", label="Login / Sign Up")
