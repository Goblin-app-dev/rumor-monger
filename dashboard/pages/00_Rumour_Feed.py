"""
Warhammer 40k 11th Edition Leak Intelligence System – Main Dashboard
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

st.set_page_config(
    page_title="WH40k 11th Ed Leak Intel",
    page_icon="⚔️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  .block-container { padding-top: 1.5rem; }
  .rumour-card {
    background: #1a1a2e;
    border: 1px solid #2a2a4a;
    border-left: 4px solid #666;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
  }
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
  .conf-bar-bg  { background:#2a2a4a; border-radius:4px; height:6px; width:100%; margin-top:6px; }
  .conf-bar-fill{ height:6px; border-radius:4px; }
  .claim-title  { font-size:1rem; font-weight:600; color:#fff; margin:6px 0 2px 0; }
  .claim-text   { font-size:0.85rem; color:#aaa; margin:0 0 4px 0; line-height:1.4; }
  .meta-text    { font-size:0.75rem; color:#888; }
</style>
""", unsafe_allow_html=True)

STATUS_CONFIG = {
    "confirmed":       {"label": "✅ Confirmed",      "color": "#00c853", "score": 100},
    "likely":          {"label": "🟢 Likely",          "color": "#64dd17", "score": 75},
    "plausible":       {"label": "🟡 Plausible",       "color": "#ffd600", "score": 50},
    "unsubstantiated": {"label": "🟠 Unsubstantiated", "color": "#ff6d00", "score": 20},
    "debunked":        {"label": "⛔ Debunked",        "color": "#d50000", "score": 0},
    "unreviewed":      {"label": "⚪ Unreviewed",      "color": "#777777", "score": 10},
}

# ── DB guard ──────────────────────────────────────────────────────────────────
if not os.environ.get("DATABASE_URL"):
    try:
        import streamlit as st2
        url = st2.secrets.get("DATABASE_URL", "")
        if url:
            os.environ["DATABASE_URL"] = url
    except Exception:
        pass

if not os.environ.get("DATABASE_URL"):
    st.error("DATABASE_URL is not set.")
    st.code('DATABASE_URL = "postgresql://..."', language="toml")
    st.stop()

try:
    from backend.db import get_engine
    with get_engine().connect():
        pass
except Exception as e:
    st.error(f"Cannot connect to database: {e}")
    st.stop()

from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source


@st.cache_data(ttl=60)
def load_claims():
    db = SessionLocal()
    try:
        rows = []
        for c in db.query(Claim).order_by(Claim.id.desc()).all():
            ev = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).count()
            rows.append({
                "id":           c.id,
                "text":         c.text,
                "ai_title":     c.ai_title or "",
                "ai_summary":   c.ai_summary or "",
                "status":       c.status,
                "faction":      c.ai_faction or c.faction or "",
                "mechanic":     c.mechanic_type or "",
                "ev_count":     ev,
                "summarized":   c.summarized_at is not None,
            })
        return rows
    finally:
        db.close()


@st.cache_data(ttl=60)
def load_stats():
    db = SessionLocal()
    try:
        return {
            "total":    db.query(Claim).count(),
            "docs":     db.query(Document).count(),
            "sources":  db.query(Source).count(),
            "confirmed":db.query(Claim).filter(Claim.status=="confirmed").count(),
            "likely":   db.query(Claim).filter(Claim.status=="likely").count(),
            "plausible":db.query(Claim).filter(Claim.status=="plausible").count(),
        }
    finally:
        db.close()


# ── Detail view ───────────────────────────────────────────────────────────────
params = st.query_params
if "claim" in params:
    claim_id = int(params["claim"])
    db = SessionLocal()
    try:
        c = db.query(Claim).filter_by(id=claim_id).first()
        if not c:
            st.error(f"Claim #{claim_id} not found.")
            st.stop()

        cfg   = STATUS_CONFIG.get(c.status, STATUS_CONFIG["unreviewed"])
        score = cfg["score"]

        if st.button("← Back to Rumour Feed"):
            st.query_params.clear()
            st.rerun()

        # ── Header ────────────────────────────────────────────────────────────
        st.markdown(f"## {c.ai_title or 'Rumour #' + str(c.id)}")

        col1, col2, col3, col4 = st.columns([2,1,1,1])
        col1.markdown(f"**Status:** {cfg['label']}")
        ev_count = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).count()
        col2.metric("Evidence Sources", ev_count)
        col3.metric("Faction", c.ai_faction or c.faction or "Unknown")
        col4.metric("Mechanic", c.mechanic_type or "—")

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

        # ── AI Summary ────────────────────────────────────────────────────────
        if c.ai_summary:
            st.markdown("### 🤖 AI Summary")
            st.markdown(c.ai_summary)

            if c.ai_confidence:
                st.markdown("**Confidence Analysis**")
                st.info(c.ai_confidence)
        else:
            st.markdown("### Claim")
            st.markdown(f"> {c.text}")
            st.caption("_(AI summary not yet generated — add GEMINI_API_KEY to enable)_")

        st.divider()

        # ── Raw claim ─────────────────────────────────────────────────────────
        with st.expander("📄 Raw extracted text"):
            st.markdown(f"_{c.text}_")

        st.divider()

        # ── Evidence ──────────────────────────────────────────────────────────
        evidence = db.query(ClaimEvidence).filter(ClaimEvidence.claim_id == c.id).all()
        st.markdown(f"### Evidence ({len(evidence)} source{'s' if len(evidence)!=1 else ''})")

        if not evidence:
            st.info("No evidence linked yet.")
        else:
            for i, ev in enumerate(evidence, 1):
                doc = db.query(Document).filter_by(id=ev.document_id).first()
                src = db.query(Source).filter_by(id=doc.source_id).first() if doc else None
                icon = {"youtube":"📺","warhammer_community":"🏛️"}.get(
                    src.platform if src else "", "💬")
                rep = f"{src.reputation_score:.0%}" if src else "?"
                label = ("✅ Official GW Source" if src and src.platform=="warhammer_community"
                         else f"{src.handle if src else '?'}")
                with st.expander(f"{icon} [{i}] {label} — reputation {rep}"):
                    if doc:
                        if doc.title: st.markdown(f"**{doc.title[:100]}**")
                        if doc.url:   st.markdown(f"[Open original ↗]({doc.url})")
                        st.caption(f"Type: {doc.document_type} | Platform: {src.platform if src else '?'}")
                        st.text_area("Excerpt", value=(doc.raw_text or "")[:800],
                                     height=160, disabled=True, key=f"ev_{ev.id}")

        st.divider()

        # ── Manual override ───────────────────────────────────────────────────
        st.markdown("### Manual Status Override")
        statuses = ["unreviewed","unsubstantiated","plausible","likely","confirmed","debunked"]
        idx = statuses.index(c.status) if c.status in statuses else 0
        new_status = st.selectbox("Status", statuses, index=idx)
        if st.button("💾 Save"):
            c.status = new_status
            db.commit()
            st.cache_data.clear()
            st.success(f"Updated to **{new_status}**")
            st.rerun()

    finally:
        db.close()
    st.stop()


# ── Rumour feed ───────────────────────────────────────────────────────────────
st.markdown("# ⚔️ Warhammer 40k 11th Edition — Leak Intelligence")
st.caption("Live rumours tracked from Reddit, YouTube, and Warhammer Community. Click any card for full details.")

stats = load_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Rumours",     stats["total"])
c2.metric("Plausible+",        stats["plausible"] + stats["likely"] + stats["confirmed"])
c3.metric("Docs Scanned",      stats["docs"])
c4.metric("Sources",           stats["sources"])
c5.metric("Confirmed (GW)",    stats["confirmed"])

st.divider()

all_claims = load_claims()

if not all_claims:
    st.info("No claims yet — trigger the **Leak Intel Pipeline** in GitHub Actions.")
    st.markdown("[Go to Actions →](https://github.com/Goblin-app-dev/rumor-monger/actions)")
    st.stop()

# ── Filters ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns([2,2,2,3])
status_opts   = ["All"] + [s for s in ["confirmed","likely","plausible","unsubstantiated","debunked","unreviewed"]
                            if any(r["status"]==s for r in all_claims)]
sel_status    = col1.selectbox("Status", status_opts)
all_factions  = sorted({r["faction"] for r in all_claims if r["faction"]})
sel_faction   = col2.selectbox("Faction", ["All"] + all_factions)
all_mechanics = sorted({r["mechanic"] for r in all_claims if r["mechanic"]})
sel_mechanic  = col3.selectbox("Mechanic", ["All"] + all_mechanics)
search        = col4.text_input("🔍 Search", placeholder="toughness, stratagem…")

filtered = all_claims
if sel_status   != "All": filtered = [r for r in filtered if r["status"]   == sel_status]
if sel_faction  != "All": filtered = [r for r in filtered if r["faction"]  == sel_faction]
if sel_mechanic != "All": filtered = [r for r in filtered if r["mechanic"] == sel_mechanic]
if search:
    lo = search.lower()
    filtered = [r for r in filtered if lo in r["text"].lower()
                or lo in r["ai_title"].lower() or lo in r["ai_summary"].lower()]

STATUS_ORDER = {"confirmed":0,"likely":1,"plausible":2,"unreviewed":3,"unsubstantiated":4,"debunked":5}
filtered.sort(key=lambda r: (STATUS_ORDER.get(r["status"],9), -r["ev_count"]))

st.caption(f"Showing **{len(filtered)}** of {len(all_claims)} rumours")

# ── Cards ─────────────────────────────────────────────────────────────────────
for row in filtered:
    cfg   = STATUS_CONFIG.get(row["status"], STATUS_CONFIG["unreviewed"])
    score = cfg["score"]

    # Use AI title if available, else truncate raw text
    title   = row["ai_title"] if row["ai_title"] else row["text"][:80]
    summary = row["ai_summary"][:160] + "…" if len(row["ai_summary"]) > 160 else row["ai_summary"]
    if not summary:
        summary = row["text"][:160] + ("…" if len(row["text"]) > 160 else "")

    tags = " · ".join(filter(None, [row["faction"], row["mechanic"]]))

    col_card, col_btn = st.columns([10, 1])
    with col_card:
        st.markdown(f"""
        <div class="rumour-card" style="border-left-color:{cfg['color']}">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px">
            <span class="badge badge-{row['status']}">{cfg['label']}</span>
            <span class="meta-text">#{row['id']} · {row['ev_count']} source{'s' if row['ev_count']!=1 else ''}{' · ' + tags if tags else ''}{' · 🤖' if row['summarized'] else ''}</span>
          </div>
          <div class="claim-title">{title}</div>
          <div class="claim-text">{summary}</div>
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
