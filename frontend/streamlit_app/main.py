"""
NotesRAG-Chatbot — Streamlit frontend.

Run with:
    streamlit run frontend/streamlit_app/main.py
"""
from __future__ import annotations

import time
from typing import List

import streamlit as st

from frontend.streamlit_app import api_client as api

st.set_page_config(
    page_title="NotesRAG Chatbot",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------- session state ---------------------------
if "messages" not in st.session_state:
    st.session_state.messages: List[dict] = []
if "use_mpc" not in st.session_state:
    st.session_state.use_mpc = False
if "top_k" not in st.session_state:
    st.session_state.top_k = 5

# --------------------------- sidebar ---------------------------------
with st.sidebar:
    st.title("📚 NotesRAG")
    st.caption("Retrieval-Augmented Study Assistant")

    page = st.radio(
        "Navigation",
        ["💬 Chat", "📤 Upload Notes", "🔍 Search", "🗂 Browse Hierarchy", "ℹ About"],
        index=0,
    )

    st.divider()
    st.subheader("Settings")
    st.session_state.top_k = st.slider("top_k retrieval", 1, 15, st.session_state.top_k)
    st.session_state.use_mpc = st.toggle(
        "Privacy-preserving (MPC)",
        value=st.session_state.use_mpc,
        help="Route the query through the simulated MPC module.",
    )

    st.divider()
    try:
        health = api.ping()
        st.success(f"API healthy ✓\nmodel: `{health.get('model')}`")
    except Exception as e:
        st.error(f"API unreachable: {e}")


# --------------------------- helpers ---------------------------------
def _render_sources(sources: list[dict]) -> None:
    if not sources:
        return
    with st.expander(f"📎 Sources ({len(sources)})", expanded=False):
        for i, s in enumerate(sources, start=1):
            md = s.get("metadata", {}) or {}
            title = md.get("title") or "(untitled)"
            st.markdown(
                f"**[Source {i}]** *note_id={s.get('note_id')}* — "
                f"score `{s.get('score', 0):.3f}` — {title}"
            )
            st.code(s.get("excerpt", "")[:600], language="markdown")


# --------------------------- pages -----------------------------------
def page_chat() -> None:
    st.header("💬 Ask your notes")
    st.caption(
        "Ask anything about the notes you've uploaded — answers are "
        "grounded in your knowledge base."
    )

    # Render history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                _render_sources(msg["sources"])

    prompt = st.chat_input("Ask a question about your notes…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("_NotesRAG is thinking…_ ⏳")
            try:
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                    if m["role"] in {"user", "assistant"}
                ]
                result = api.ask(
                    prompt,
                    top_k=st.session_state.top_k,
                    history=history,
                    use_mpc=st.session_state.use_mpc,
                )
                # naive typing animation
                full = result.get("answer", "(empty response)")
                shown = ""
                for ch in full:
                    shown += ch
                    if len(shown) % 8 == 0:
                        placeholder.markdown(shown + "▌")
                        time.sleep(0.005)
                placeholder.markdown(full)
                _render_sources(result.get("sources", []))
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": full,
                        "sources": result.get("sources", []),
                    }
                )
            except Exception as e:
                placeholder.error(f"Request failed: {e}")


def page_upload() -> None:
    st.header("📤 Upload notes")
    tab1, tab2 = st.tabs(["📁 File", "🌐 URL"])

    def _meta_inputs(prefix: str) -> dict:
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Subject", key=f"{prefix}_subject")
            topic = st.text_input("Topic", key=f"{prefix}_topic")
            difficulty = st.selectbox(
                "Difficulty", ["easy", "medium", "hard"], index=1, key=f"{prefix}_diff"
            )
            content_type = st.selectbox(
                "Content type",
                ["notes", "qna", "handwritten", "quiz", "exam"],
                index=0,
                key=f"{prefix}_ctype",
                help=(
                    "notes — lecture notes / textbook prose\n"
                    "qna — question-and-answer pairs\n"
                    "handwritten — scanned/handwritten PDF (forces OCR)\n"
                    "quiz — quiz-style Q&A\n"
                    "exam — exam paper with questions + marks"
                ),
            )
        with col2:
            unit = st.text_input("Unit / Chapter", key=f"{prefix}_unit")
            subtopic = st.text_input("Subtopic", key=f"{prefix}_subtopic")
            tags = st.text_input("Tags (comma-separated)", key=f"{prefix}_tags")
            force_ocr = st.checkbox(
                "Force OCR (slow, scanned PDFs only)",
                value=False,
                key=f"{prefix}_force_ocr",
            )
        return {
            "subject": subject,
            "unit": unit,
            "topic": topic,
            "subtopic": subtopic,
            "difficulty": difficulty,
            "tags": tags,
            "content_type": content_type,
            "force_ocr": "true" if force_ocr else "false",
        }

    with tab1:
        meta = _meta_inputs("file")
        file = st.file_uploader(
            "Upload PDF / DOCX / OneNote-JSON",
            type=["pdf", "docx", "json"],
            accept_multiple_files=False,
        )
        if st.button("Ingest file", type="primary", disabled=not file):
            if not all([meta["subject"], meta["unit"], meta["topic"], meta["subtopic"]]):
                st.error("Subject, Unit, Topic and Subtopic are required.")
            else:
                with st.spinner("Ingesting…"):
                    try:
                        result = api.upload_file(file, meta)
                        st.success(
                            f"Ingested **{result['title']}** "
                            f"({result['note_count']} notes, "
                            f"{result['chunks_indexed']} chunks indexed)."
                        )
                        st.json(result)
                    except Exception as e:
                        st.error(f"Upload failed: {e}")

    with tab2:
        meta_u = _meta_inputs("url")
        url = st.text_input("URL", placeholder="https://example.com/article")
        if st.button("Ingest URL", type="primary", disabled=not url):
            if not all([meta_u["subject"], meta_u["unit"], meta_u["topic"], meta_u["subtopic"]]):
                st.error("Subject, Unit, Topic and Subtopic are required.")
            else:
                with st.spinner("Fetching & ingesting…"):
                    try:
                        result = api.upload_url(url, meta_u)
                        st.success(f"Ingested {result['title']}")
                        st.json(result)
                    except Exception as e:
                        st.error(f"Upload failed: {e}")


def page_search() -> None:
    st.header("🔍 Search notes")
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        q = st.text_input("Query", placeholder="e.g. context switching overhead")
    with col2:
        mode = st.selectbox("Mode", ["semantic", "text"], index=0)
    with col3:
        limit = st.number_input("Limit", min_value=1, max_value=50, value=10)

    if st.button("Search", type="primary", disabled=not q.strip()):
        try:
            data = api.search(q, mode=mode, limit=int(limit))
            results = data.get("results", [])
            st.caption(f"{len(results)} result(s) — mode: {data.get('mode')}")
            for i, r in enumerate(results, start=1):
                title = r.get("title") or r.get("metadata", {}).get("title") or f"Note {r.get('note_id', r.get('id'))}"
                excerpt = r.get("excerpt") or r.get("content", "")
                with st.container(border=True):
                    st.markdown(f"**{i}. {title}**")
                    if "score" in r:
                        st.caption(f"score: {r['score']:.3f}")
                    st.write(excerpt[:600] + ("…" if len(excerpt) > 600 else ""))
        except Exception as e:
            st.error(f"Search failed: {e}")


def page_browse() -> None:
    st.header("🗂 Browse hierarchy")
    try:
        subjects = api.list_subjects()
    except Exception as e:
        st.error(f"Cannot load subjects: {e}")
        return

    if not subjects:
        st.info("No subjects yet — upload some notes first.")
        return

    sub_names = [s["name"] for s in subjects]
    chosen = st.selectbox("Subject", sub_names)
    sub = next(s for s in subjects if s["name"] == chosen)

    units = api.list_units(subject_id=sub["id"])
    if not units:
        st.info("No units under this subject yet.")
        return

    for u in units:
        with st.expander(f"📘 {u['name']}  ({u.get('topic_count', 0)} topics)"):
            topics = api.list_topics(unit_id=u["id"])
            if not topics:
                st.caption("_no topics yet_")
            for t in topics:
                st.markdown(
                    f"- **{t['name']}** — "
                    f"{t.get('subtopic_count', 0)} subtopic(s)"
                )


def page_about() -> None:
    st.header("ℹ About NotesRAG")
    st.markdown(
        """
        **NotesRAG** is a retrieval-augmented chatbot for structured
        academic notes. It ingests PDFs, DOCX files, web pages, and
        OneNote-style JSON exports; chunks and embeds them with
        `bge-large-en-v1.5`; stores vectors in FAISS; and answers
        questions with Anthropic's Claude API.

        - 🔐 Optional MPC mode simulates privacy-preserving retrieval
          across multiple parties.
        - 🗂 Hierarchical schema: *Subject → Unit → Topic → Subtopic → Note*
        - 🐍 Python-only — Flask backend + Streamlit frontend.

        Built as a study companion. PRs welcome.
        """
    )


# --------------------------- router ----------------------------------
{
    "💬 Chat": page_chat,
    "📤 Upload Notes": page_upload,
    "🔍 Search": page_search,
    "🗂 Browse Hierarchy": page_browse,
    "ℹ About": page_about,
}[page]()
