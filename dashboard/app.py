"""
Streamlit entry point — redirects to the Rumour Feed page.
Preserves any query params (e.g. ?claim=123) so detail links work.
"""
import streamlit as st
st.switch_page("pages/00_🏠_Rumour_Feed.py")
