"""
Page 1 – Full Claims Browser with clickable detail links.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import pandas as pd
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence

st.set_page_config(page_title="Claims Browser", page_icon="📋", layout="wide")
st.title("📋 Claims Browser")
st.caption("All extracted rumours. Use filters, then click 'Detail' to drill in.")

STATUS_CONFIG = {
    "confirmed":       {"label": "✅ Confirmed",      "color": "#00c853"},
    "likely":          {"label": "🟢 Likely",          "color": "#64dd17"},
    "plausible":       {"label": "🟡 Plausible",       "color": "#ffd600"},
    "unsubstantiated": {"label": "🟠 Unsubstantiated", "color": "#ff6d00"},
    "debunked":        {"label": "⛔ Debunked",        "color": "#d50000"},
    "unreviewed":      {"label": "⚪ Unreviewed",      "color": "#777777"},
}

@st.cache_data(ttl=30)
def load():
    db = SessionLocal()
    try:
        rows = []
        for c in db.query(Claim).order_by(Claim.id.desc()).all():
            ev = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).count()
            rows.append({
                "id":       c.id,
                "status":   c.status,
                "faction":  c.faction or "—",
                "mechanic": c.mechanic_type or "—",
                "ev":       ev,
                "text":     c.text,
                "preview":  c.text[:110] + ("…" if len(c.text)>110 else ""),
            })
        return rows
    finally:
        db.close()

all_rows = load()
df = pd.DataFrame(all_rows)

# ── Filters ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns([2,2,2,3])
sel_status   = c1.selectbox("Status",   ["All"] + sorted(df["status"].unique()))
sel_faction  = c2.selectbox("Faction",  ["All"] + sorted(df["faction"].unique()))
sel_mechanic = c3.selectbox("Mechanic", ["All"] + sorted(df["mechanic"].unique()))
search       = c4.text_input("🔍 Search", placeholder="keyword…")

filtered = all_rows
if sel_status   != "All": filtered = [r for r in filtered if r["status"]   == sel_status]
if sel_faction  != "All": filtered = [r for r in filtered if r["faction"]  == sel_faction]
if sel_mechanic != "All": filtered = [r for r in filtered if r["mechanic"] == sel_mechanic]
if search:
    lo = search.lower()
    filtered = [r for r in filtered if lo in r["text"].lower()]

st.caption(f"{len(filtered)} of {len(all_rows)} rumours")

# ── Table + detail buttons ────────────────────────────────────────────────────
hdr = st.columns([1, 2, 2, 1, 7, 1])
for col, label in zip(hdr, ["ID","Status","Faction","Sources","Claim Preview","→"]):
    col.markdown(f"**{label}**")
st.markdown("---")

for row in filtered:
    cfg = STATUS_CONFIG.get(row["status"], STATUS_CONFIG["unreviewed"])
    cols = st.columns([1, 2, 2, 1, 7, 1])
    cols[0].write(row["id"])
    cols[1].markdown(
        f"<span style='color:{cfg['color']};font-weight:700'>{cfg['label']}</span>",
        unsafe_allow_html=True
    )
    cols[2].write(row["faction"])
    cols[3].write(row["ev"])
    cols[4].write(row["preview"])
    if cols[5].button("→", key=f"cb_{row['id']}"):
        # Navigate to main app with claim param
        st.markdown(
            f'<meta http-equiv="refresh" content="0;url=/?claim={row["id"]}">',
            unsafe_allow_html=True
        )
