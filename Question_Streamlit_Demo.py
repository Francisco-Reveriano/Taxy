import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
# -----------------------------------------------------------------------------
# 0. Sidebar: Clear Conversation Button
# -----------------------------------------------------------------------------
with st.sidebar:
    if st.button("Clear Conversation"):
        # Reset all chat‐related session state variables
        st.session_state.messages = []
        st.session_state.responses = []
        st.session_state.question_index = 0
        # Force a rerun so that everything is cleared immediately
        st.rerun()
# -----------------------------------------------------------------------------
# 1. Initialize/Reset Session State
# -----------------------------------------------------------------------------
if "question_index" not in st.session_state:
    st.session_state.question_index = 0  # Tracks which question to ask next :contentReference[oaicite:4]{index=4}

if "responses" not in st.session_state:
    st.session_state.responses = []  # Store raw answers (optional) :contentReference[oaicite:5]{index=5}

if "messages" not in st.session_state:
    st.session_state.messages = []  # Maintains the entire chat history :contentReference[oaicite:6]{index=6}

client = OpenAI()

# -----------------------------------------------------------------------------
# 2. Redisplay Existing Chat History (Assistant & User)
# -----------------------------------------------------------------------------
for msg in st.session_state.messages:
    # Each msg is a dict: {"role": "assistant" or "user", "content": "..."}
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
# -----------------------------------------------------------------------------
# 3. Define Your List of Questions (Static)
# -----------------------------------------------------------------------------
QUESTIONS = [
    "What is your preferred email address?",
    "What is your correct filing status for 2010 (Single, Married Filing Jointly, etc.)?",
    "How many dependents, if any, are you claiming?",
    "What is your occupation/title with Hall Ltd Group?",
    "If married, please provide your spouse’s full name, occupation, and birth year."
]
# -----------------------------------------------------------------------------
# 4. Determine Current Question Index
# -----------------------------------------------------------------------------
idx = st.session_state.question_index

# -----------------------------------------------------------------------------
# 4.1. If All Questions Were Answered, Show a Summary and Stop
# -----------------------------------------------------------------------------
if idx >= len(QUESTIONS):
    st.write("## Thank you! Here are your responses:")
    final_responses = {}
    for i, ans in enumerate(st.session_state.responses):
        final_responses[f"**Q{i+1}:** {QUESTIONS[i]}"] = f"**A{i+1}:** {ans}"
        st.write(
            f"**Q{i+1}:** {QUESTIONS[i]}  \n"
            f"**A{i+1}:** {ans}"
        )
    st.stop()  # Prevent any further input :contentReference[oaicite:7]{index=7}
    print(final_responses)

# -----------------------------------------------------------------------------
# 4.2. Only Rewrite & Render the Question Once
# -----------------------------------------------------------------------------
# Check if the assistant’s question at index 'idx' has already been asked:
# For each completed Q&A we append exactly two entries to `messages`: the assistant’s question
# and then the user’s answer. Thus, when len(messages) <= 2 * idx, it means we have not yet
# asked question #idx. :contentReference[oaicite:8]{index=8}
if len(st.session_state.messages) <= 2 * idx:
    current_question = QUESTIONS[idx]
    # Call the OpenAI rewriter exactly once for this question
    rewrite_question = client.chat.completions.create(
        model="gpt-3.5-turbo",
        stream=True,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful question rewriter. Rewrite each question in a new, user‐friendly format."
            },
            {"role": "user", "content": current_question}
        ]
    )
    # Render the assistant's message exactly once
    with st.chat_message("assistant"):
        response = st.write_stream(rewrite_question)
    st.session_state.messages.append(
        {"role": "assistant", "content": response}
    )

# -----------------------------------------------------------------------------
# 5. Capture the User’s Answer to the Current Question
# -----------------------------------------------------------------------------
# We still show a single chat_input widget for the user to type their answer,
# even if the assistant’s question has already been rendered.
if user_input := st.chat_input("Type your answer here..."):
    # 5.1. Display the user's response in chat format
    st.session_state.messages.append({"role": "user", "content": user_input})

    # 5.2. Store the raw response (optional, but keeps a separate list)
    st.session_state.responses.append(user_input)

    # 5.3. Move to the next question index
    st.session_state.question_index += 1

    # 5.4. Force a rerun so that on the next script execution the next question is processed
    st.rerun()  # Guarantees that the next question is asked immediately :contentReference[oaicite:10]{index=10}
