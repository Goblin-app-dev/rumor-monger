"""
Page 2 – Claim Detail
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

st.set_page_config(page_title="Claim Detail", page_icon="🔍", layout="wide")
st.title("🔍 Claim Detail")

db = SessionLocal()
try:
    total = db.query(Claim).count()
finally:
    db.close()

if total == 0:
    st.info("No claims yet — trigger the **Leak Intel Pipeline** in GitHub Actions first.")
    st.markdown("[Go to Actions →](https://github.com/Goblin-app-dev/rumor-monger/actions)")
    st.stop()

claim_id = st.number_input("Claim ID", min_value=1, step=1, value=1)

db = SessionLocal()
try:
    claim = db.query(Claim).filter_by(id=int(claim_id)).first()
    if not claim:
        st.error(f"No claim found with ID {claim_id}.")
        st.stop()

    STATUS_BADGE = {
        "confirmed":       "✅ Confirmed",
        "likely":          "🟢 Likely",
        "plausible":       "🟡 Plausible",
        "unsubstantiated": "🟠 Unsubstantiated",
        "debunked":        "⛔ Debunked",
        "unreviewed":      "⚪ Unreviewed",
    }

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status",   STATUS_BADGE.get(claim.status, claim.status))
    col2.metric("Edition",  claim.edition or "11th")
    col3.metric("Faction",  claim.faction or "—")
    col4.metric("Mechanic", claim.mechanic_type or "—")

    st.subheader("Claim Text")
    st.markdown(f"> {claim.text}")
    if claim.unit_or_rule:
        st.caption(f"**Unit / Rule:** {claim.unit_or_rule}")

    st.divider()

    evidence_rows = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
    st.subheader(f"Evidence ({len(evidence_rows)} source{'s' if len(evidence_rows) != 1 else ''})")

    if not evidence_rows:
        st.warning("No evidence linked to this claim yet.")
    else:
        for ev in evidence_rows:
            doc = db.query(Document).filter_by(id=ev.document_id).first()
            src = db.query(Source).filter_by(id=doc.source_id).first() if doc else None
            platform_icon = "📺" if src and src.platform == "youtube" else ("🏛️" if src and src.platform == "warhammer_community" else "💬")
            with st.expander(
                f"{platform_icon} [{ev.evidence_type.upper()}] "
                f"{doc.title[:80] if doc and doc.title else 'Document'} "
                f"— {src.handle if src else '?'}"
            ):
                if doc:
                    if doc.url:
                        st.markdown(f"[Open original]({doc.url})")
                    if src:
                        st.caption(f"Platform: {src.platform} | Reputation: {src.reputation_score:.0%}")
                    st.text_area("Raw text excerpt", value=(doc.raw_text or "")[:600],
                                 height=150, disabled=True, key=f"ev_{ev.id}")

    st.divider()
    st.subheader("Manual Status Override")
    statuses = ["unreviewed", "unsubstantiated", "plausible", "likely", "confirmed", "debunked"]
    cur_idx = statuses.index(claim.status) if claim.status in statuses else 0
    new_status = st.selectbox("Set status", statuses, index=cur_idx)
    if st.button("💾 Save"):
        claim.status = new_status
        db.commit()
        st.cache_data.clear()
        st.success(f"Updated to **{new_status}**")
        st.rerun()
finally:
    db.close()
