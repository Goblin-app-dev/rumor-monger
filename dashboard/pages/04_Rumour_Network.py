"""
Page 4 – Rumour Network graph
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import streamlit as st
import networkx as nx
import plotly.graph_objects as go
from backend.db import SessionLocal
from backend.models import Claim, ClaimEvidence, Document, Source

st.set_page_config(page_title="Rumour Network", page_icon="🕸️", layout="wide")
st.title("🕸️ Rumour Network")
st.caption("Nodes = claims (coloured by status) and sources. Edges = evidence links.")

db = SessionLocal()
try:
    claims   = db.query(Claim).all()
    sources  = db.query(Source).all()
    evidence = db.query(ClaimEvidence).all()
    docs     = {d.id: d for d in db.query(Document).all()}
finally:
    db.close()

if not claims:
    st.info("No data yet — trigger the **Leak Intel Pipeline** in GitHub Actions first.")
    st.markdown("[Go to Actions →](https://github.com/Goblin-app-dev/rumor-monger/actions)")
    st.stop()

STATUS_COLOR = {
    "confirmed":       "#00c853",
    "likely":          "#64dd17",
    "plausible":       "#ffd600",
    "unsubstantiated": "#ff6d00",
    "debunked":        "#d50000",
    "unreviewed":      "#9e9e9e",
}

G = nx.Graph()
for c in claims:
    G.add_node(f"claim_{c.id}", kind="claim",
               label=f"C{c.id}: {c.text[:40]}…",
               color=STATUS_COLOR.get(c.status, "#9e9e9e"), size=12)
for s in sources:
    G.add_node(f"src_{s.id}", kind="source",
               label=f"{s.platform}:{s.handle}", color="#1565c0", size=8)
for ev in evidence:
    doc = docs.get(ev.document_id)
    if doc:
        G.add_edge(f"claim_{ev.claim_id}", f"src_{doc.source_id}")

# Limit to top 100 claims if graph is huge
if G.number_of_nodes() > 200:
    top_ids = sorted([c.id for c in claims],
                     key=lambda cid: sum(1 for e in evidence if e.claim_id == cid),
                     reverse=True)[:100]
    keep = {f"claim_{cid}" for cid in top_ids} | {f"src_{s.id}" for s in sources}
    G = G.subgraph(keep).copy()

pos = nx.spring_layout(G, seed=42, k=0.5)

edge_x, edge_y = [], []
for u, v in G.edges():
    x0, y0 = pos[u]; x1, y1 = pos[v]
    edge_x += [x0, x1, None]; edge_y += [y0, y1, None]

node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
for node in G.nodes():
    x, y = pos[node]
    d = G.nodes[node]
    node_x.append(x); node_y.append(y)
    node_text.append(d.get("label", node))
    node_color.append(d.get("color", "#9e9e9e"))
    node_size.append(d.get("size", 8))

fig = go.Figure(
    data=[
        go.Scatter(x=edge_x, y=edge_y, mode="lines",
                   line=dict(width=0.8, color="#555"), hoverinfo="none"),
        go.Scatter(x=node_x, y=node_y, mode="markers+text",
                   text=node_text, textposition="top center",
                   marker=dict(color=node_color, size=node_size,
                               line=dict(width=1, color="#fff")),
                   hovertext=node_text, hoverinfo="text"),
    ],
    layout=go.Layout(
        showlegend=False, hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        height=700, margin=dict(l=0, r=0, t=0, b=0),
    ),
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("""
**Node colours:**
🟢 Confirmed &nbsp;|&nbsp; 🟡 Likely &nbsp;|&nbsp; 🟠 Plausible &nbsp;|&nbsp;
🔴 Unsubstantiated &nbsp;|&nbsp; ⛔ Debunked &nbsp;|&nbsp; ⚪ Unreviewed &nbsp;|&nbsp; 🔵 Source
""")
