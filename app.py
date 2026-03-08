"""
app.py

Minimal Streamlit UI for the BI Agent.
- Maintains conversation history
- Calls run_agent()
- Displays tool trace per assistant message
"""

import streamlit as st
from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import run_agent


# ------------------------------------------------------------
# Page setup
# ------------------------------------------------------------

st.set_page_config(page_title="BI Agent", layout="wide")
st.title("📊 Business Intelligence Assistant")


# ------------------------------------------------------------
# Session state
# ------------------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []   # rendered chat messages (role + content dicts)

if "history" not in st.session_state:
    st.session_state.history = []    # BaseMessage objects passed to the agent

if "traces" not in st.session_state:
    st.session_state.traces = []     # one tool trace list per assistant message


# ------------------------------------------------------------
# Clear conversation button
# ------------------------------------------------------------

if st.button("Clear conversation"):
    st.session_state.messages = []
    st.session_state.history = []
    st.session_state.traces = []
    st.rerun()


# ------------------------------------------------------------
# Render chat history
# ------------------------------------------------------------

# track assistant messages separately so each maps to the right trace index
assistant_idx = 0

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        if msg["role"] == "assistant":
            trace = (
                st.session_state.traces[assistant_idx]
                if assistant_idx < len(st.session_state.traces)
                else []
            )
            if trace:
                with st.expander("Agent actions"):
                    for step in trace:
                        st.write(
                            f"• {step.get('tool_name')} "
                            f"({step.get('duration_ms')} ms)"
                        )
            assistant_idx += 1  # advance only for assistant messages, not user ones


# ------------------------------------------------------------
# Chat input
# ------------------------------------------------------------

user_input = st.chat_input("Ask about pipeline, revenue, deals...")

if user_input:

    # show user message immediately
    st.session_state.messages.append(
        {"role": "user", "content": user_input}
    )
    st.session_state.history.append(
        HumanMessage(content=user_input)
    )

    with st.chat_message("user"):
        st.markdown(user_input)

    # run agent and display response
    with st.chat_message("assistant"):
        with st.spinner("Fetching live data..."):
            try:
                result = run_agent(
                    user_message=user_input,
                    chat_history=st.session_state.history[:-1],  # exclude the message we just added
                )

                answer = result.get("answer", "No response returned.")
                trace  = result.get("tool_trace", [])

                st.markdown(answer)

                if trace:
                    with st.expander("Agent actions"):
                        for step in trace:
                            st.write(
                                f"• {step.get('tool_name')} "
                                f"({step.get('duration_ms')} ms)"
                            )

                # persist assistant turn
                st.session_state.messages.append(
                    {"role": "assistant", "content": answer}
                )
                st.session_state.traces.append(trace)
                st.session_state.history.append(
                    AIMessage(content=answer)
                )

            except Exception as e:
                error_msg = f"Error: {e}"
                st.markdown(error_msg)

                st.session_state.messages.append(
                    {"role": "assistant", "content": error_msg}
                )
                st.session_state.traces.append([])
                st.session_state.history.append(
                    AIMessage(content=error_msg)
                )