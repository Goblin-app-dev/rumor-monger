"""
Page 3 – Sources Intel
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
import plotly.express as px
from backend.db import SessionLocal
from backend.models import Source, Document

st.set_page_config(page_title="Sources Intel", page_icon="🕵️", layout="wide")
st.title("🕵️ Sources Intel")

@st.cache_data(ttl=30)
def load():
    db = SessionLocal()
    try:
        rows = []
        for s in db.query(Source).all():
            dc = db.query(Document).filter(Document.source_id == s.id).count()
            rows.append({"ID": s.id, "Platform": s.platform,
                         "Handle": s.handle, "URL": s.url or "",
                         "Docs": dc, "Reputation": round(s.reputation_score or 0.5, 2)})
        return rows
    finally:
        db.close()

rows = load()
df = pd.DataFrame(rows)

sel = st.selectbox("Platform", ["All","reddit","youtube"])
view = df if sel == "All" else df[df["Platform"]==sel]
st.caption(f"{len(view)} sources")

edited = st.data_editor(
    view[["ID","Platform","Handle","Docs","Reputation"]],
    column_config={"Reputation": st.column_config.NumberColumn(
        min_value=0.0, max_value=1.0, step=0.05, format="%.2f")},
    disabled=["ID","Platform","Handle","Docs"],
    hide_index=True, use_container_width=True, key="src_editor"
)

if st.button("💾 Save Reputation Scores"):
    db2 = SessionLocal()
    try:
        for _, r in edited.iterrows():
            s = db2.query(Source).filter_by(id=int(r["ID"])).first()
            if s: s.reputation_score = float(r["Reputation"])
        db2.commit()
        st.cache_data.clear()
        st.success("Saved.")
    except Exception as e:
        db2.rollback(); st.error(str(e))
    finally:
        db2.close()

st.divider()
if not df.empty:
    pc = df.groupby("Platform")["Docs"].sum().reset_index()
    fig = px.pie(pc, names="Platform", values="Docs", title="Documents by Platform",
                 color_discrete_sequence=["#7B2D8B","#C41E3A"])
    st.plotly_chart(fig, use_container_width=True)
