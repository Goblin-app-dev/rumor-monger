"""
Warhammer 40k 11th Edition Leak Intelligence System – Main Dashboard
Home page: rumour feed with confidence indicators. Click any rumour to drill in.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

st.set_page_config(
    page_title="WH40k 11th Ed Leak Intel",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Hide default Streamlit header padding */
  .block-container { padding-top: 1.5rem; }

  /* Rumour card */
  .rumour-card {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-left: 4px solid #666;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
    cursor: pointer;
    transition: border-color 0.2s;
  }
  .rumour-card:hover { border-color: #7b68ee; }

  .badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }
  .badge-confirmed       { background:#00c853; color:#000; }
  .badge-likely          { background:#64dd17; color:#000; }
  .badge-plausible       { background:#ffd600; color:#000; }
  .badge-unsubstantiated { background:#ff6d00; color:#fff; }
  .badge-debunked        { background:#d50000; color:#fff; }
  .badge-unreviewed      { background:#555; color:#fff; }

  .conf-bar-bg {
    background: #2a2a4a;
    border-radius: 4px;
    height: 6px;
    width: 100%;
    margin-top: 6px;
  }
  .conf-bar-fill {
    height: 6px;
    border-radius: 4px;
  }
  .claim-text {
    font-size: 0.92rem;
    color: #e0e0e0;
    margin: 6px 0 4px 0;
    line-height: 1.45;
  }
  .meta-text {
    font-size: 0.75rem;
    color: #888;
  }
</style>
""", unsafe_allow_html=True)

STATUS_CONFIG = {
    "confirmed":       {"label": "✅ Confirmed",       "color": "#00c853", "score": 100},
    "likely":          {"label": "🟢 Likely",           "color": "#64dd17", "score": 75},
    "plausible":       {"label": "🟡 Plausible",        "color": "#ffd600", "score": 50},
    "unsubstantiated": {"label": "🟠 Unsubstantiated",  "color": "#ff6d00", "score": 20},
    "debunked":        {"label": "⛔ Debunked",         "color": "#d50000", "score": 0},
    "unreviewed":      {"label": "⚪ Unreviewed",       "color": "#777777", "score": 10},
}

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(ttl=30)
def load_claims():
    db = SessionLocal()
    try:
        claims = db.query(Claim).order_by(Claim.id.desc()).all()
        rows = []
        for c in claims:
            ev_count = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).count()
            rows.append({
                "id":           c.id,
                "text":         c.text,
                "status":       c.status,
                "faction":      c.faction,
                "mechanic":     c.mechanic_type,
                "unit":         c.unit_or_rule,
                "edition":      c.edition,
                "ev_count":     ev_count,
                "created_at":   str(c.created_at)[:10] if c.created_at else "—",
            })
        return rows
    finally:
        db.close()

@st.cache_data(ttl=30)
def load_stats():
    db = SessionLocal()
    try:
        return {
            "total_claims":  db.query(Claim).count(),
            "total_docs":    db.query(Document).count(),
            "total_sources": db.query(Source).count(),
            "confirmed":     db.query(Claim).filter(Claim.status=="confirmed").count(),
            "likely":        db.query(Claim).filter(Claim.status=="likely").count(),
            "plausible":     db.query(Claim).filter(Claim.status=="plausible").count(),
            "unsubstantiated": db.query(Claim).filter(Claim.status=="unsubstantiated").count(),
            "debunked":      db.query(Claim).filter(Claim.status=="debunked").count(),
        }
    finally:
        db.close()

# ── Route: detail view ────────────────────────────────────────────────────────
# ── DB connectivity guard ────────────────────────────────────────────────────
import os
if not os.environ.get("DATABASE_URL"):
    st.error("DATABASE_URL is not set. Add it in Streamlit Cloud → App settings → Secrets.")
    st.code('[secrets]\nDATABASE_URL = "postgresql://user:pass@host:5432/dbname"', language="toml")
    st.stop()

try:
    from backend.db import engine
    with engine.connect() as _conn:
        pass
except Exception as _e:
    st.error(f"Cannot connect to the database: {_e}")
    st.info("Make sure DATABASE_URL in your Streamlit secrets points to a live Postgres instance (e.g. Supabase).")
    st.stop()

params = st.query_params
if "claim" in params:
    claim_id = int(params["claim"])
    db = SessionLocal()
    try:
        claim = db.query(Claim).filter_by(id=claim_id).first()
        if not claim:
            st.error(f"Claim #{claim_id} not found.")
            st.stop()

        cfg = STATUS_CONFIG.get(claim.status, STATUS_CONFIG["unreviewed"])
        score = cfg["score"]

        # ── Back button ───────────────────────────────────────────────────────
        if st.button("← Back to Rumour Feed"):
            st.query_params.clear()
            st.rerun()

        st.markdown(f"## Rumour #{claim.id}")

        # ── Header row ────────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns([2,1,1,1])
        c1.markdown(f"**Status:** {cfg['label']}")
        c2.metric("Evidence Sources", db.query(ClaimEvidence).filter(ClaimEvidence.claim_id==claim.id).count())
        c3.metric("Faction", claim.faction or "Unknown")
        c4.metric("Mechanic", claim.mechanic_type or "—")

        # Confidence bar
        st.markdown(f"""
        <div style="margin:8px 0 16px 0">
          <div style="font-size:0.8rem;color:#aaa;margin-bottom:4px">
            Confidence: <b style="color:{cfg['color']}">{score}%</b>
          </div>
          <div class="conf-bar-bg">
            <div class="conf-bar-fill" style="width:{score}%;background:{cfg['color']}"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Full claim text ───────────────────────────────────────────────────
        st.markdown("### Full Claim")
        st.markdown(f"> {claim.text}")

        if claim.unit_or_rule:
            st.caption(f"Unit / Rule detected: **{claim.unit_or_rule}**")

        st.divider()

        # ── Evidence list ─────────────────────────────────────────────────────
        evidence = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == claim.id).all()
        st.markdown(f"### Evidence ({len(evidence)} source{'s' if len(evidence)!=1 else ''})")

        if not evidence:
            st.info("No evidence linked yet. Re-run the pipeline to find more sources.")
        else:
            for i, ev in enumerate(evidence, 1):
                doc = db.query(Document).filter_by(id=ev.document_id).first()
                src = db.query(Source).filter_by(id=doc.source_id).first() if doc else None

                platform_icon = "📺" if src and src.platform == "youtube" else "💬"
                ev_label = "Transcript" if ev.evidence_type == "transcript" else "Post/Comment"
                handle = src.handle if src else "unknown"
                rep = f"{src.reputation_score:.0%}" if src else "?"

                with st.expander(
                    f"{platform_icon} [{i}] {ev_label} — {handle}  |  reputation {rep}"
                ):
                    if doc:
                        col1, col2 = st.columns(2)
                        col1.caption(f"**Type:** {doc.document_type}")
                        col2.caption(f"**Platform:** {src.platform.upper() if src else '?'}")

                        if doc.title:
                            st.markdown(f"**Source:** {doc.title[:100]}")
                        if doc.url:
                            st.markdown(f"[Open original]({doc.url})")

                        # Highlight the claim text inside the raw excerpt
                        raw = (doc.raw_text or "")[:800]
                        st.text_area("Raw text excerpt", value=raw, height=160,
                                     disabled=True, key=f"ev_text_{ev.id}")

        st.divider()

        # ── Manual override ───────────────────────────────────────────────────
        st.markdown("### Manual Status Override")
        statuses = ["unreviewed","unsubstantiated","plausible","likely","confirmed","debunked"]
        cur_idx = statuses.index(claim.status) if claim.status in statuses else 0
        new_status = st.selectbox("Set status", statuses, index=cur_idx, key="override_sel")
        if st.button("💾 Save"):
            claim.status = new_status
            db.commit()
            st.cache_data.clear()
            st.success(f"Status updated to **{new_status}**")
            st.rerun()

    finally:
        db.close()
    st.stop()

# ── Main rumour feed ──────────────────────────────────────────────────────────
st.markdown("# ⚔️ Warhammer 40k 11th Edition — Leak Intelligence")
st.caption("Live rumours tracked from Reddit and YouTube. Click any card to see full details.")

stats = load_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Rumours",    stats["total_claims"])
c2.metric("Plausible+",       stats["plausible"] + stats["likely"] + stats["confirmed"])
c3.metric("Documents Scanned",stats["total_docs"])
c4.metric("Sources Tracked",  stats["total_sources"])
c5.metric("Confirmed",        stats["confirmed"])

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
all_claims = load_claims()

col1, col2, col3, col4 = st.columns([2,2,2,3])
status_opts = ["All"] + [s for s in ["confirmed","likely","plausible","unsubstantiated","debunked","unreviewed"]
                         if any(r["status"]==s for r in all_claims)]
sel_status  = col1.selectbox("Status", status_opts)

all_factions = sorted({r["faction"] for r in all_claims if r["faction"]})
sel_faction  = col2.selectbox("Faction", ["All"] + all_factions)

all_mechanics = sorted({r["mechanic"] for r in all_claims if r["mechanic"]})
sel_mechanic  = col3.selectbox("Mechanic", ["All"] + all_mechanics)

search_text = col4.text_input("🔍 Search claim text", placeholder="e.g. toughness, stratagem…")

# Apply filters
filtered = all_claims
if sel_status  != "All": filtered = [r for r in filtered if r["status"]  == sel_status]
if sel_faction != "All": filtered = [r for r in filtered if r["faction"] == sel_faction]
if sel_mechanic!= "All": filtered = [r for r in filtered if r["mechanic"]== sel_mechanic]
if search_text:
    lo = search_text.lower()
    filtered = [r for r in filtered if lo in r["text"].lower()]

st.caption(f"Showing **{len(filtered)}** of {len(all_claims)} rumours")

# ── Sort ──────────────────────────────────────────────────────────────────────
STATUS_ORDER = {"confirmed":0,"likely":1,"plausible":2,"unreviewed":3,"unsubstantiated":4,"debunked":5}
filtered.sort(key=lambda r: (STATUS_ORDER.get(r["status"], 9), -r["ev_count"]))

# ── Render cards ──────────────────────────────────────────────────────────────
if not filtered:
    st.warning("No rumours match the current filters.")
else:
    for row in filtered:
        cfg   = STATUS_CONFIG.get(row["status"], STATUS_CONFIG["unreviewed"])
        score = cfg["score"]
        short = row["text"][:160] + ("…" if len(row["text"]) > 160 else "")
        tags  = " · ".join(filter(None, [row["faction"], row["mechanic"]]))

        col_card, col_btn = st.columns([10, 1])
        with col_card:
            st.markdown(f"""
            <div class="rumour-card" style="border-left-color:{cfg['color']}">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
                <span class="badge badge-{row['status']}">{cfg['label']}</span>
                <span class="meta-text">#{row['id']} · {row['ev_count']} source{'s' if row['ev_count']!=1 else ''}{' · ' + tags if tags else ''}</span>
              </div>
              <div class="claim-text">{short}</div>
              <div class="conf-bar-bg">
                <div class="conf-bar-fill" style="width:{score}%;background:{cfg['color']}"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

        with col_btn:
            st.markdown("<div style='margin-top:18px'></div>", unsafe_allow_html=True)
            if st.button("Details", key=f"btn_{row['id']}"):
                st.query_params["claim"] = str(row["id"])
                st.rerun()
