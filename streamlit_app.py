import streamlit as st

st.set_page_config(page_title="Online Job Portal", layout="wide")

st.title("💼 Online Job Portal")
st.subheader("Free Deployment Demo")

st.write("""
This is a **Streamlit demo** of the Online Job Portal.

Full backend (Flask + DB) runs locally or on PythonAnywhere.
""")

st.markdown("### 🔑 Login")
username = st.text_input("Username")
password = st.text_input("Password", type="password")

if st.button("Login"):
    if username and password:
        st.success(f"Welcome, {username}!")
    else:
        st.error("Please enter credentials")

st.markdown("---")
st.info("🚀 Deployed FREE using Streamlit Cloud")
