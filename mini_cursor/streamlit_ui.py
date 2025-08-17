import uuid
import requests
import streamlit as st

st.set_page_config(page_title="AI Chatbot", page_icon="💬", layout="centered")

# ---------- Session state ----------
if "loading" not in st.session_state:
    st.session_state.loading = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_turn_id" not in st.session_state:
    st.session_state.active_turn_id = None
if "just_cleared" not in st.session_state:
    st.session_state.just_cleared = False
if "chat_input" not in st.session_state:
    st.session_state.chat_input = ""

# ---------- Top bar ----------
top = st.container()
with top:
    col1, col2 = st.columns([8, 2], vertical_alignment="center")

    with col1:
        st.markdown(
            """
            <h1 style="
                color:#1E90FF;
                text-align:left;
                font-family: 'Trebuchet MS','Lucida Sans Unicode','Lucida Grande','Lucida Sans',Arial,sans-serif;
                font-size:38px;
                margin: 0;              /* important: no negative margins */
                pointer-events: none;    /* important: don't block clicks */
            ">
                💬 Chat with Agent
            </h1>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        
        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        
        if st.button("🗑️ Clear Chat", key="clear_btn", disabled=st.session_state.loading):
            st.session_state.messages = []
            st.session_state.loading = False
            st.session_state.active_turn_id = None
            st.session_state.chat_input = ""
            st.session_state.just_cleared = True
            st.rerun()


# ---------- Render chat history ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("raw") is not None:
            with st.expander("Raw response JSON"):
                st.json(msg["raw"])

# ---------- Input ----------
query = st.chat_input(
    "Enter your instruction...",
    key="chat_input",
    disabled=st.session_state.loading,
)

# ---------- On user submit ----------
if query and not st.session_state.loading and not st.session_state.just_cleared:
    st.session_state.loading = True
    st.session_state.messages.append({"role": "user", "content": query})
    st.session_state.active_turn_id = str(uuid.uuid4())
    st.rerun()

# ---------- If we just added a user message, call backend ----------
if (
    st.session_state.messages
    and st.session_state.loading
    and not st.session_state.just_cleared
    and st.session_state.messages[-1]["role"] == "user"
):
    user_msg = st.session_state.messages[-1]["content"]
    try:
        with st.spinner("Waiting for response..."):
            resp = requests.post(
                "http://localhost:8000/chat",
                json={
                    "query": user_msg,
                    "history": st.session_state.messages,
                    "turn_id": st.session_state.active_turn_id,
                },
                timeout=90,
            )
            resp.raise_for_status()
            payload = resp.json()

        answer = payload.get("answer", "")
        st.session_state.messages.append({"role": "assistant", "content": answer})
    except requests.RequestException as e:
        st.session_state.messages.append(
            {"role": "assistant", "content": f" Request failed: {e}"}
        )
    finally:
        st.session_state.loading = False
        st.session_state.active_turn_id = None
        st.rerun()

# ---------- One-cycle guard reset ----------
if st.session_state.just_cleared:
    st.session_state.just_cleared = False
