import streamlit as st
from database import supabase
from sidebar import render_sidebar

st.set_page_config(page_title="Search Doctors - MediAI", layout="wide")

render_sidebar()

st.markdown("""
    <style>
        div[data-testid="stMain"] .stButton button {
            min-height: 52px;
            font-size: 16px;
            font-weight: 700;
        }
        .doctor-meta {
            color: #4b5563;
            margin: -0.25rem 0 0.75rem 0;
        }
        .doctor-meta strong {
            color: #2563eb;
        }
    </style>
""", unsafe_allow_html=True)

st.title("Search Doctors")
st.write("")
st.write("")

col1, col2, col3 = st.columns([2, 1.5, 1.5], gap="large")

with col1:
    search_query = st.text_input("Search doctor by name...", "")
with col2:
    try:
        spec_res = supabase.table("specialties").select("name").execute()
        specialties_list = ["All Specialties"] + [item['name'] for item in spec_res.data] if spec_res.data else [
            "All Specialties"]
    except Exception:
        st.error("Could not load specialties. Please check the database connection and try again.")
        specialties_list = ["All Specialties"]
    selected_spec = st.selectbox("Specialty", specialties_list)
with col3:
    selected_sort = st.selectbox("Sort by", ["Recommended", "Top Rated", "Most Reviewed"])

st.write("")
st.divider()
st.write("")


@st.cache_data(ttl=60)
def get_doctors(specialty):
    query_fields = "id, full_name, stamp, specialties(name), reviews_summary(average_rating, review_count, summary)"

    if specialty == "All Specialties":
        docs_res = supabase.table("doctors").select(query_fields).execute()
    else:
        spec_id_res = supabase.table("specialties").select("id").eq("name", specialty).execute()
        if not spec_id_res.data: return []
        spec_id = spec_id_res.data[0]['id']
        docs_res = supabase.table("doctors").select(query_fields).eq("specialty_id", spec_id).execute()

    doctors = docs_res.data if docs_res.data else []

    if doctors:
        doc_ids = [doc['id'] for doc in doctors]
        rev_res = supabase.table("reviews").select("doctor_id, stars, consistency_score").in_("doctor_id", doc_ids).execute()
        all_reviews = rev_res.data if rev_res.data else []

        reviews_by_doc = {}
        for r in all_reviews:
            reviews_by_doc.setdefault(r['doctor_id'], []).append(r)

        for doc in doctors:
            d_revs = reviews_by_doc.get(doc['id'], [])
            if not d_revs:
                doc['rec_score'] = 0.0
                continue

            total = len(d_revs)

            avg_stars = sum(r['stars'] for r in d_revs) / total
            stars_points = (avg_stars / 5.0) * 45.0

            avg_trust_raw = sum(
                (r['consistency_score'] if r['consistency_score'] is not None else 0.5) for r in d_revs) / total
            trust_points = avg_trust_raw * 45.0

            popularity_points = min(10.0, total * 2.0)

            doc['rec_score'] = round(stars_points + trust_points + popularity_points, 1)

    return doctors


try:
    all_doctors = get_doctors(selected_spec)
except Exception:
    st.error("Could not load doctors. Please check the database connection and try again.")
    st.stop()

filtered_docs = [doc for doc in all_doctors if search_query.lower() in doc['full_name'].lower()]

if selected_sort == "Recommended":
    filtered_docs.sort(key=lambda x: x.get('rec_score', 0.0), reverse=True)
elif selected_sort == "Top Rated":
    filtered_docs.sort(key=lambda x: (x['reviews_summary']['average_rating'] if x['reviews_summary'] else 0.0),
                       reverse=True)
elif selected_sort == "Most Reviewed":
    filtered_docs.sort(key=lambda x: (x['reviews_summary']['review_count'] if x['reviews_summary'] else 0),
                       reverse=True)

if not filtered_docs:
    st.info("No doctors match your search criteria.")
else:
    for doc in filtered_docs:
        stats = doc['reviews_summary'] or {"average_rating": 0.0, "review_count": 0, "summary": "No data"}
        spec_name = doc.get('specialties', {}).get('name', 'General Practice')
        average_rating = float(stats.get('average_rating') or 0.0)
        review_count = int(stats.get('review_count') or 0)
        rec_score = float(doc.get('rec_score', 0.0))

        with st.container(border=True):
            c1, c2 = st.columns([4, 1.2], gap="large")
            with c1:
                st.subheader(doc['full_name'])
                st.markdown(
                    f"<div class='doctor-meta'><strong>{spec_name}</strong> | Stamp Code: {doc['stamp']}</div>",
                    unsafe_allow_html=True
                )

                metric_cols = st.columns(3)
                metric_cols[0].metric("Rating", f"{average_rating:.1f} / 5")
                metric_cols[1].metric("Reviews", review_count)
                metric_cols[2].metric(
                    "AI Score",
                    f"{rec_score:.1f}%",
                    help="Based on rating, review consistency, and popularity."
                )
            with c2:
                st.write("")
                st.write("")
                if st.button("View Profile", key=f"btn_{doc['id']}", use_container_width=True):
                    st.session_state.selected_doctor = doc
                    st.switch_page("pages/2_Profile.py")

        st.write("")
