import streamlit as st

st.set_page_config(page_title="Online Job Portal", layout="wide")

st.title("Online Job Portal")
st.write("This is a demo dashboard for my Flask-based Online Job Portal project.")

st.subheader("Features")
st.markdown("""
- Role-based login: student, recruiter, admin  
- Resume upload and job applications  
- Recruiter job posting and application tracking  
""")

st.subheader("How to run full project")
st.markdown("""
The full backend is built with **Flask**.  
Source code: [GitHub repo](https://github.com/vamsivalluri-19/online-job-portal)
""")
