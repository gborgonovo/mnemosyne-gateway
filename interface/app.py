import streamlit as st
import sys
import os
from datetime import datetime
import yaml
import importlib
import logging
from dotenv import load_dotenv

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/mnemosyne.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Force reload for development
from core import graph_manager, attention, perception, initiative, llm
import workers.gardener
importlib.reload(graph_manager)
importlib.reload(attention)
importlib.reload(perception)
importlib.reload(initiative)
importlib.reload(llm)
importlib.reload(workers.gardener)

from core.graph_manager import GraphManager
from core.attention import AttentionModel
from core.perception import PerceptionModule
from core.initiative import InitiativeEngine
from core.feedback import FeedbackManager
from core.llm import get_llm_provider
from workers.gardener import Gardener

st.set_page_config(page_title="Mnemosyne", layout="wide")
st.cache_resource.clear()

# Helper function to load config
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

@st.cache_resource
def get_core_modules():
    # Force reload of core modules to pick up changes
    import core.graph_manager
    import core.perception
    import core.attention
    import core.initiative
    import core.llm
    import core.feedback
    
    importlib.reload(core.graph_manager)
    importlib.reload(core.perception)
    importlib.reload(core.attention)
    importlib.reload(core.initiative)
    importlib.reload(core.llm)
    importlib.reload(core.feedback)
    
    config = load_config()
    
    # 1. Base Graph
    gm = core.graph_manager.GraphManager(config['graph']['uri'], config['graph']['user'], config['graph']['password'])
    
    # 2. Attention & Decay
    am = core.attention.AttentionModel(gm, config=config.get('attention', {}))
    
    # 3. LLM Provider (Selection logic handled in core.llm)
    llm = core.llm.get_llm_provider(config)
    
    # 4. Perception (needs GM, LLM, and AM)
    pm = core.perception.PerceptionModule(gm, llm, am)
    
    # 5. Initiative & Feedback
    ie = core.initiative.InitiativeEngine(gm, config=config)
    fm = core.feedback.FeedbackManager(gm)
    
    # 6. Gardener
    gardener_worker = workers.gardener.Gardener(gm, llm, am, config=config)
    
    return gm, am, pm, ie, fm, gardener_worker, llm

gm, am, pm, ie, fm, gardener, llm_instance = get_core_modules() # Updated unpacking to include llm_instance

st.title("🧠 Mnemosyne: Cognitive Partner")

if not gm:
    st.error("Could not connect to the Connectome (Neo4j). Ensure the database is running.")
    st.stop()

# Sidebar: Stats and Initiatives
with st.sidebar:
    st.title("Status")
    st.success("Connected to Connectome")
    
    all_nodes = gm.get_all_nodes()
    st.metric("Total Nodes", len(all_nodes))
    
    active_nodes = gm.get_active_nodes(threshold=0.1)
    st.metric("Active Nodes (>0.1)", len(active_nodes))
    
    st.divider()
    st.subheader("💡 Mnemosyne Says...")
    
    # Initialize initiatives in session state if not present
    if "current_initiatives" not in st.session_state:
        st.session_state.current_initiatives = ie.generate_initiatives()
    
    if st.session_state.current_initiatives:
        # Use a list of indices to safely remove items while iterating
        for idx, init in enumerate(st.session_state.current_initiatives):
            st.info(init['message'])
            col_u, col_d = st.columns([1, 1])
            with col_u:
                if st.button("👍", key=f"up_{idx}_{init['target']}"):
                    fm.record_feedback(init['source'], init['target'], 1)
                    st.session_state.current_initiatives.pop(idx)
                    st.success("Feedback positivo registrato.")
                    st.rerun()
            with col_d:
                if st.button("👎", key=f"down_{idx}_{init['target']}"):
                    fm.record_feedback(init['source'], init['target'], -1)
                    st.session_state.current_initiatives.pop(idx)
                    st.warning("Feedback negativo registrato. Non te lo proporrò più.")
                    st.rerun()
    else:
        st.write("Silenzio cognitivo. Tutto procede regolarmente.")

# Main Interface: Chat and Graph
tab1, tab2, tab3 = st.tabs(["💬 Chat", "🕸️ Connectome", "🧹 Gardener"])

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
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)
        
        # 1. Update Graph (Perception)
        entities = pm.process_input(user_input)
        
        # 1b. Check for Simulation Trigger (Sandbox Reasoning)
        impact_context = ""
        # Simple heuristic: if user says "se modificassi", "se cambiassi", "impatto di"
        trigger_keywords = ["se modificassi", "se cambiassi", "impatto di", "cosa succede se"]
        if any(kw in user_input.lower() for kw in trigger_keywords) and entities:
            # Assume first entity is the target of simulation
            target = entities[0]
            depth = config.get("retrieval", {}).get("impact_depth", 3)
            chains = gm.trace_dependencies(target, max_depth=depth)
            if chains:
                impact_context = f"L'impatto di una modifica a '{target}' coinvolgerebbe:\n"
                for c in chains:
                    impact_context += f"- {' -> '.join(c['chain'])}\n"

        # 1c. Get Semantic Context (Knowledge Retrieval)
        # Fetch details for the nodes touched by perception to ground The Butler's response
        semantic_context = ""
        
        # DEBUG: Show extracted entities in sidebar
        st.sidebar.write(f"DEBUG - Entities extracted: {entities}")
        
        if entities:
            semantic_context = "=== USER'S PROJECT CONTEXT (from Mnemosyne Memory) ===\n"
            semantic_context += "CRITICAL: Use THIS data, not generic definitions.\n\n"
            
            for entity_name in entities:
                node = gm.get_node(entity_name)
                if node:
                    semantic_context += f"📍 Entity: '{entity_name}'\n"
                
                # Get Neighbors
                neighbors = gm.get_neighbors(entity_name)
                if neighbors:
                    limit = config.get("retrieval", {}).get("neighbors_limit", 5)
                    semantic_context += f"   Connected to: "
                    semantic_context += ", ".join([f"{n['node']['name']}" for n in neighbors[:limit]]) 
                    semantic_context += "\n"
                
                # Get OBSERVATIONS (user's original text)
                with gm.driver.session() as session:
                    obs_limit = config.get("retrieval", {}).get("observation_limit", 3)
                    text_limit = config.get("retrieval", {}).get("observation_text_limit", 150)
                    obs_query = f"""
                    MATCH (n)-[:MENTIONED_IN]->(o:Observation)
                    WHERE toLower(n.name) = toLower($name)
                    RETURN o.content as content
                    ORDER BY o.timestamp DESC LIMIT {obs_limit}
                    """
                    results = session.run(obs_query, name=entity_name)
                    observations = [record['content'] for record in results]
                    if observations:
                        semantic_context += f"   📝 User said:\n"
                        for obs in observations:
                            semantic_context += f"      - \"{obs[:text_limit]}...\"\n" if len(obs) > text_limit else f"      - \"{obs}\"\n"
                semantic_context += "\n"
        
        # DEBUG: Show in persistent expander
        with st.sidebar.expander("🔍 DEBUG Info", expanded=False):
            st.write(f"**Entities extracted:** {entities}")
            st.write(f"**Semantic Context:**")
            st.code(semantic_context if semantic_context else "EMPTY", language="text")

        # 2. Get Proactive Context (Initiative)
        proactive_context = ie.get_proactive_context()
        
        # 3. Generate The Butler's Response (LLM)
        with st.chat_message("assistant"):
            response = pm.llm.generate_response(user_input, proactive_context, impact_context, semantic_context)
            st.write(response)
        
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Rerun to update the sidebar/graph view
        st.rerun()

    # Feedback logic for Side Suggestions (if any were generated/displayed)
    # Note: For MVP we are only showing initiatives in Sidebar, but we want to capture feedback on them.
    # The initiative engine 'messages' are currently just strings.
    # To properly support feedback, we need Initiatives to be structured with source/target metadata in the UI.
    
    # Let's add feedback buttons to the SIDEBAR initiatives for now

with tab2:
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Manual Stimulation")
        if all_nodes:
            target_node = st.selectbox("Select Node", [n['name'] for n in all_nodes if "Observation" not in n['labels']], key="stim_select")
            boost = st.slider("Boost Amount", 0.1, 1.0, 0.5)
            if st.button("Stimulate"):
                am.stimulate([target_node], boost_amount=boost)
                st.rerun()
            
            if st.button("Apply Decay (Time Step)"):
                am.apply_decay()
                st.rerun()
            
            if st.button("Reset All Heat (Cold Start)", type="secondary"):
                with gm.driver.session() as session:
                    session.run("MATCH (n) SET n.activation_level = 0.0")
                st.success("All nodes cooled down.")
                st.rerun()
        else:
            st.info("No nodes in graph yet.")

    with col2:
        st.subheader("Active Nodes Heatmap")
        if active_nodes:
            # Filter out generic Observation nodes from the heatmap visualization
            visual_nodes = [n for n in active_nodes if "Observation" not in n['labels']]
            
            # Sort by activation
            sorted_nodes = sorted(visual_nodes, key=lambda x: x['activation'], reverse=True)
            for n in sorted_nodes:
                val = n['activation']
                st.write(f"**{n['name']}**: {val:.2f}")
                st.progress(val)
        else:
            st.info("No active nodes.")

        st.divider()
        st.subheader("🌫️ Forgotten Topics (Dormant)")
        # Nodes with activation < 0.1 but > 0
        dormant_nodes = [n for n in all_nodes if 0 < n.get('activation', 0) < 0.1 and "Observation" not in n['labels']]
        if dormant_nodes:
            for n in dormant_nodes:
                st.write(f"- {n['name']} ({n['activation']:.2f})")
        else:
            st.info("Nessun argomento nel dimenticatoio.")

    st.divider()
    st.subheader("🕵️ Epistemic Memory")
    
    subtab_hist, subtab_search = st.tabs(["🕒 Recent History", "🔍 Search by Node"])
    
    with subtab_hist:
        with gm.driver.session() as session:
            query = "MATCH (o:Observation) RETURN o.content as content, o.timestamp as ts ORDER BY o.timestamp DESC LIMIT 10"
            results = session.run(query)
            all_obs = [dict(record) for record in results]
        
        if all_obs:
            for obs in all_obs:
                st.write(f"**[{obs['ts'][:16]}]** {obs['content']}")
        else:
            st.info("Nessuna osservazione registrata.")

    with subtab_search:
        if all_nodes:
            selectable_nodes = [n['name'] for n in all_nodes if "Observation" not in n['labels']]
            selected_node = st.selectbox("Explore context for:", selectable_nodes, key="context_select")
            
            with gm.driver.session() as session:
                query = """
                MATCH (n {name: $name})-[r:MENTIONED_IN]->(o:Observation)
                RETURN o.content as content, o.timestamp as ts
                ORDER BY o.timestamp DESC
                """
                results = session.run(query, name=selected_node)
                node_obs = [dict(record) for record in results]
                
            if node_obs:
                for obs in node_obs:
                    with st.expander(f"Mentioned on {obs['ts'][:16]}"):
                        st.write(f"*{obs['content']}*")
            else:
                st.info(f"Nessun contesto specifico trovato per **{selected_node}**.")

with tab3:
    st.subheader("🧹 Il Giardiniere (Graph Hygiene)")
    st.info("Manutenzione automatica dei concetti e rimozione ridondanze.")
    
    if st.button("Esegui Ciclo Manutenzione (Decay + Analisi)"):
        with st.spinner("Il Giardiniere sta lavorando..."):
            gardener.run_once()
        st.success("Manutenzione completata: decadimento applicato e nuovi duplicati cercati.")
        st.rerun()
    
    st.divider()
    with gm.driver.session() as session:
        # Use id(a) < id(b) and DISTINCT to avoid reciprocal or multiple duplicates.
        # CRITICAL: Exclude technical Observation nodes from the suggestions list.
        query = """
        MATCH (a)-[r:MAYBE_SAME_AS]-(b) 
        WHERE id(a) < id(b) 
          AND NOT "Observation" IN labels(a) 
          AND NOT "Observation" IN labels(b)
        RETURN DISTINCT a.name as name1, b.name as name2, id(a) as id1, id(b) as id2
        """
        results = session.run(query)
        duplicates = [dict(record) for record in results]
        
    if duplicates:
        st.warning("Potenziali duplicati semantici rilevati:")
        for idx, dup in enumerate(duplicates):
            col_a, col_b, col_c = st.columns([3, 1, 1])
            with col_a:
                st.write(f"**{dup['name1']}** ↔️ **{dup['name2']}**")
            with col_b:
                # Use a combined ID key to be absolutely unique
                if st.button("Merge", key=f"merge_{dup['id1']}_{dup['id2']}"):
                    gm.merge_nodes(dup['id2'], dup['id1']) 
                    st.success(f"Unito {dup['name1']} in {dup['name2']}")
                    st.rerun()
            with col_c:
                if st.button("Ignora", key=f"ignore_{dup['id1']}_{dup['id2']}"):
                    with gm.driver.session() as session:
                        session.run("MATCH (a)-[r:MAYBE_SAME_AS]-(b) WHERE id(a) = $id1 AND id(b) = $id2 DELETE r", id1=dup['id1'], id2=dup['id2'])
                    st.info("Suggerimento rimosso.")
                    st.rerun()
            st.divider()
    else:
        st.info("Il grafo è pulito. Nessun duplicato rilevato.")
