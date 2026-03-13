import streamlit as st
import database
import mnemosyne_api
import llm_client
from config_reader import get_tester_prompt

st.set_page_config(page_title="Mnemosyne Chat", page_icon="🧠", layout="wide")

st.title("🧠 The Butler - Mnemosyne Chat")

# --- INITIALIZATION ---
if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None

# --- SIDEBAR ---
with st.sidebar:
    st.header("Conversazioni")
    
    if st.button("➕ Nuova Conversazione", use_container_width=True):
        new_id = database.create_chat()
        st.session_state.current_chat_id = new_id
        st.rerun()
        
    st.divider()
    
    chats = database.get_chats()
    for chat in chats:
        # Highlight active chat
        button_type = "primary" if str(chat["id"]) == str(st.session_state.current_chat_id) else "secondary"
        
        col1, col2 = st.sidebar.columns([0.8, 0.2])
        
        with col1:
            if st.button(chat["title"], key=f"chat_{chat['id']}", type=button_type, use_container_width=True):
                st.session_state.current_chat_id = str(chat["id"])
                st.rerun()
        
        with col2:
            if st.button("🗑️", key=f"del_{chat['id']}", help="Elimina conversazione"):
                database.delete_chat(str(chat["id"]))
                if st.session_state.current_chat_id == str(chat["id"]):
                    st.session_state.current_chat_id = None
                st.rerun()

# --- MAIN CHAT AREA ---
if st.session_state.current_chat_id:
    chat_id = st.session_state.current_chat_id
    messages = database.get_messages(chat_id)
    
    # Display message history
    for msg in messages:
        # We don't display system messages in the UI usually
        if msg["role"] in ["user", "assistant"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
    # Chat Input
    if prompt := st.chat_input("Scrivi un messaggio..."):
        # 1. Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
            
        # 2. Save user message to SQLite
        database.add_message(chat_id, "user", prompt)
        
        # 3. Retrieve Context from Mnemosyne
        with st.status("Interrogando Mnemosyne...", expanded=False) as status:
            mnemosyne_context = mnemosyne_api.generate_context_from_query(prompt)
            status.update(label="Memorie recuperate", state="complete", expanded=False)
            
        # 4. Prepare messages for LLM
        base_prompt = get_tester_prompt()
        if mnemosyne_context:
            system_content = f"{base_prompt}\n\n[MNEMOSYNE MEMORY RETRIEVAL]\n{mnemosyne_context}"
        else:
            system_content = base_prompt
            
        llm_messages = [{"role": "system", "content": system_content}]
        
        # Add history (limit to last 10 messages to avoid blowing up context, adjust as needed)
        recent_history = [
            {"role": m["role"], "content": m["content"]} 
            for m in database.get_messages(chat_id)[-10:]
            if m["role"] in ["user", "assistant"]
        ]
        llm_messages.extend(recent_history)
        
        # 5. Generate and stream response
        with st.chat_message("assistant"):
            stream = llm_client.generate_chat_stream(llm_messages)
            full_response = st.write_stream(stream)
            
        # 6. Save assistant message
        database.add_message(chat_id, "assistant", full_response)
        
        # 7. Add to Mnemosyne memory for continuous learning
        mnemosyne_api.add_memory(prompt, full_response)
        
        # 8. Generate title if it's the first exchange
        if len(messages) == 0: # Because `messages` was loaded before these new additions
            new_title = llm_client.generate_chat_title(llm_messages)
            database.update_chat_title(chat_id, new_title)
            st.rerun() # Refresh sidebar to show new title
else:
    st.info("👈 Seleziona o crea una 'Nuova Conversazione' dalla barra laterale per iniziare.")
    
    # Optionally display the briefing on the empty state
    with st.expander("ℹ️ Briefing di Mnemosyne"):
        briefing = mnemosyne_api.fetch_briefing()
        if briefing:
            st.markdown(briefing)
        else:
            st.write("Nessun briefing disponibile.")
