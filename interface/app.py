import streamlit as st
import sys
import os
import requests
import json
import yaml
import pandas as pd
import plotly.graph_objects as go
import networkx as nx
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Gateway Configuration
GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4001")

st.set_page_config(page_title="Mnemosyne Dashboard", layout="wide")

# Helper functions for Gateway API
def api_get(endpoint, params=None):
    try:
        response = requests.get(f"{GATEWAY_URL}{endpoint}", params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # st.error(f"Gateway Error (GET {endpoint}): {e}")
        return None

def api_post(endpoint, data=None, files=None, params=None):
    try:
        response = requests.post(f"{GATEWAY_URL}{endpoint}", json=data, files=files, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Gateway Error (POST {endpoint}): {e}")
        return None

def api_delete(endpoint, params=None):
    try:
        response = requests.delete(f"{GATEWAY_URL}{endpoint}", params=params, timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Gateway Error (DELETE {endpoint}): {e}")
        return None

# Removed misplaced set_page_config
st.cache_resource.clear()

# Helper function to load config
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

# Removed local get_core_modules in favor of API calls
# gm, am, pm, ie, fm, gardener, llm_instance = get_core_modules() 

st.title("🧠 Mnemosyne: Cognitive Partner")

# Check Gateway Connection
status = api_get("/status")
if not status:
    st.error("Could not connect to the Mnemosyne Gateway. Ensure the server is running on port 4001.")
    st.stop()
elif status.get("neo4j") != "connected":
    st.warning("Gateway is running, but Neo4j is disconnected.")

# Sidebar: Stats and Initiatives
with st.sidebar:
    st.title("Gateway Status")
    status = api_get("/status")
    if status and status.get("neo4j") == "connected":
        st.success("Connected to Gateway & Connectome")
        stats = status.get("stats", {})
        st.metric("Total Nodes", stats.get("nodes", 0))
        st.metric("Total Relationships", stats.get("relationships", 0))
    else:
        st.error("Gateway Disconnected")
        if st.button("Retry Connection"):
            st.rerun()

    st.divider()
    st.subheader("💡 Suggestions")
    
    briefing = api_get("/briefing")
    if briefing and briefing.get("suggestions"):
        for sugg in briefing["suggestions"]:
            st.info(sugg)
    else:
        st.write("Silenzio cognitivo.")

# Main Interface: Tabs
tab1, tab2, tab3, tab4 = st.tabs(["💬 Chat", "🕸️ Connectome", "🧹 Gardener", "📁 Documents"])

with tab1:
    st.subheader("Talk to your Mind")
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    user_input = st.chat_input("Di cosa vuoi parlare?")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        
        # Call Gateway for observation/chat
        with st.chat_message("assistant"):
            with st.spinner("Pensando..."):
                # 1. Add observation (this triggers learning)
                # Note: Currently /add returns success. The actual response generation
                # for chat might need a separate 'chat' endpoint or we use the 'briefing' context.
                # Since we don't have a dedicated /chat endpoint yet that returns a grounded response,
                # we'll simulate the grounded response here via the Gateway's internal state if possible,
                # or just use /add and then show suggestions.
                
                # For now, let's keep it simple: inform the user what happened.
                resp = api_post("/add", data={"content": user_input})
                if resp:
                    st.write("Ho registrato la tua osservazione e sto aggiornando il Connectome.")
                    st.session_state.messages.append({"role": "assistant", "content": "Osservazione registrata."})
                else:
                    st.error("Errore di comunicazione con il Gateway.")
        st.rerun()

    # Feedback logic for Side Suggestions (if any were generated/displayed)
    # Note: For MVP we are only showing initiatives in Sidebar, but we want to capture feedback on them.
    # The initiative engine 'messages' are currently just strings.
    # To properly support feedback, we need Initiatives to be structured with source/target metadata in the UI.
    
    # Let's add feedback buttons to the SIDEBAR initiatives for now

with tab2:
    st.subheader("Visual Connectome")
    
    # Fetch active nodes/stats for visualization
    status = api_get("/status")
    if status and "stats" in status:
        # We'll use plotly to render a simple network graph
        # For a full graph we'd need all nodes and edges. 
        # For now, let's show the high-activation subgraph.
        
        st.info("Visualizzazione dinamica del grafo (Top active nodes)")
        
        # Simple NetworkX + Plotly rendering logic
        G = nx.Graph()
        
        # We need a way to get the subgraph via API. 
        # For the MVP, let's use the /history or a new /graph endpoint.
        # Since /graph doesn't exist yet, we'll show a placeholder or 
        # use the search functionality to build a local view.
        
        q = st.text_input("Search for a node to center the graph:", "")
        if q:
            data = api_get("/search", params={"q": q})
            if data:
                center = data['name']
                G.add_node(center, size=20, color='red')
                for rel in data.get('related', []):
                    # related format: "name (type)"
                    try:
                        name, rel_type = rel.rsplit(' (', 1)
                        rel_type = rel_type.rstrip(')')
                        G.add_node(name, size=10, color='blue')
                        G.add_edge(center, name, label=rel_type)
                    except:
                        pass
        
        if G.nodes():
            pos = nx.spring_layout(G)
            edge_x = []
            edge_y = []
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=0.5, color='#888'),
                hoverinfo='none',
                mode='lines')

            node_x = []
            node_y = []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode='markers+text',
                hoverinfo='text',
                text=[node for node in G.nodes()],
                marker=dict(
                    showscale=True,
                    colorscale='YlOrRd',
                    reversescale=True,
                    color=[],
                    size=10,
                    line_width=2))
            
            fig = go.Figure(data=[edge_trace, node_trace],
                         layout=go.Layout(
                            showlegend=False,
                            hovermode='closest',
                            margin=dict(b=0,l=0,r=0,t=0),
                            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Digita il nome di un concetto per iniziare l'esplorazione visiva.")
    else:
        st.error("Gateway offline o Connectome non raggiungibile.")

with tab3:
    st.subheader("🧹 Il Giardiniere (Graph Hygiene)")
    st.info("La manutenzione automatica è gestita dal Gateway.")
    if st.button("Esegui Ciclo Manutenzione"):
        # We'd need an endpoint for this. Placeholder for now.
        st.warning("Endpoint /gardener/run non ancora implementato.")
    
with tab4:
    st.subheader("📁 Gestione Documenti")
    
    # upload
    with st.expander("Carica nuovo documento", expanded=True):
        uploaded_file = st.file_uploader("Chiama un file .txt o .md", type=['txt', 'md'])
        scope = st.selectbox("Scope", ["Public", "Internal", "Private"], index=0)
        if uploaded_file and st.button("Ingest"):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            resp = api_post("/ingest", files=files, params={"scope": scope})
            if resp:
                st.success(f"Documento '{uploaded_file.name}' inviato per l'ingestione.")
                st.rerun()

    st.divider()
    st.subheader("Archivio Documenti")
    docs_resp = api_get("/documents")
    if docs_resp and docs_resp.get("documents"):
        docs = docs_resp["documents"]
        for d in docs:
            col_name, col_scope, col_actions = st.columns([3, 1, 2])
            with col_name:
                st.write(f"**{d['name']}**")
            with col_scope:
                st.caption(d['scope'])
            with col_actions:
                # Download link
                # download_url = f"{GATEWAY_URL}/document/{d['name']}/download"
                # st.markdown(f"[Download]({download_url})")
                
                # Use a button for simpler UI flow in Streamlit
                if st.button("Elimina", key=f"del_{d['name']}"):
                    del_resp = api_delete(f"/document/{d['name']}", params={"scope": d['scope']})
                    if del_resp:
                        st.success(f"Documento '{d['name']}' eliminato.")
                        st.rerun()
            st.divider()
    else:
        st.info("Nessun documento nell'archivio.")
