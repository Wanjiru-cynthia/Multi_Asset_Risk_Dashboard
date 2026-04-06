import streamlit as st
st.set_page_config(page_title="Cross-Asset Risk Intelligence", layout="wide")
st.title("Cross-Asset Risk Intelligence")
st.markdown("Navigate using the sidebar to explore the dashboard.")
st.page_link("pages/1_Overview.py", label="Overview", icon="📊")
st.page_link("pages/2_Asset_Drilldown.py", label="Asset Drilldown", icon="🔍")
st.page_link("pages/3_Event_Detail.py", label="Event Detail", icon="📋")
st.page_link("pages/4_Macro_Backdrop.py", label="Macro Backdrop", icon="🛰")
