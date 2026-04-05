"""
Page 2 – Claim Detail: full claim text + all linked evidence.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

st.set_page_config(page_title="Claim Detail", page_icon="🔍", layout="wide")
st.title("🔍 Claim Detail")

claim_id = st.number_input("Claim ID", min_value=1, step=1, value=1)

db = SessionLocal()
try:
    claim = db.query(Claim).filter_by(id=int(claim_id)).first()

    if not claim:
        st.error(f"No claim found with ID {claim_id}.")
        st.stop()

    # ── Claim header ─────────────────────────────────────────────────────────
    STATUS_BADGE = {
        "confirmed":       "🟢 Confirmed",
        "likely":          "🟡 Likely",
        "plausible":       "🟠 Plausible",
        "unsubstantiated": "🔴 Unsubstantiated",
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
        st.caption(f"**Unit / Rule detected:** {claim.unit_or_rule}")

    st.divider()

    # ── Evidence ─────────────────────────────────────────────────────────────
    evidence_rows = (
        db.query(ClaimEvidence)
        .filter(ClaimEvidence.claim_id == claim.id)
        .all()
    )

    st.subheader(f"Evidence ({len(evidence_rows)} sources)")

    if not evidence_rows:
        st.warning("No evidence linked to this claim yet.")
    else:
        for ev in evidence_rows:
            doc = db.query(Document).filter_by(id=ev.document_id).first()
            src = db.query(Source).filter_by(id=doc.source_id).first() if doc else None

            with st.expander(
                f"[{ev.evidence_type.upper()}] "
                f"{doc.title[:80] if doc and doc.title else 'Document'} "
                f"— {src.platform.upper() if src else '?'} / {src.handle if src else '?'}"
            ):
                if doc:
                    st.caption(f"Doc ID: {doc.id} | Type: {doc.document_type}")
                    if doc.url:
                        st.markdown(f"[View source]({doc.url})")
                    if src:
                        st.caption(
                            f"Source reputation: {src.reputation_score:.2f}"
                        )
                    st.text_area(
                        "Raw text excerpt",
                        value=doc.raw_text[:600] if doc.raw_text else "",
                        height=150,
                        disabled=True,
                        key=f"ev_{ev.id}",
                    )

    st.divider()

    # ── Status override ───────────────────────────────────────────────────────
    st.subheader("Manual Status Override")
    new_status = st.selectbox(
        "Set status",
        ["unreviewed", "unsubstantiated", "plausible", "likely", "confirmed", "debunked"],
        index=["unreviewed", "unsubstantiated", "plausible", "likely",
               "confirmed", "debunked"].index(claim.status)
        if claim.status in ["unreviewed", "unsubstantiated", "plausible",
                            "likely", "confirmed", "debunked"] else 0,
    )
    if st.button("Save Status"):
        claim.status = new_status
        db.commit()
        st.success(f"Status updated to **{new_status}**.")
        st.rerun()

finally:
    db.close()
