"""
Prompt templates and orchestration helpers for retrieval-augmented
generation with Claude.
"""
from __future__ import annotations

from textwrap import dedent
from typing import Tuple

SYSTEM_PROMPT = dedent(
    """
    You are NotesRAG, an academic study assistant. You answer the
    student's question using ONLY the context provided between the
    <context> tags. If the context is insufficient, say so clearly
    and suggest what kind of additional notes would help.

    Guidelines:
    - Cite sources inline using the bracket labels from the context
      (e.g., [Source 1], [Source 2]).
    - Prefer concise, structured answers. Use short paragraphs.
    - Define key terms when first introduced.
    - Never fabricate facts or citations.
    - If the student asks for a practice question or example, base it
      on the provided context.
    """
).strip()


USER_PROMPT_TEMPLATE = dedent(
    """
    <context>
    {context}
    </context>

    Question: {query}

    Answer the question using ONLY the context above. Cite sources
    inline using their bracket labels (e.g., [Source 1]). If the
    context is insufficient, say so.
    """
).strip()


def build_rag_prompt(*, query: str, context: str) -> Tuple[str, str]:
    """Build (system, user) prompts for Claude given retrieved context."""
    if not context.strip():
        context = "(No relevant notes were retrieved from the knowledge base.)"
    return SYSTEM_PROMPT, USER_PROMPT_TEMPLATE.format(
        context=context, query=query.strip()
    )


def build_summary_prompt(title: str, body: str) -> Tuple[str, str]:
    """Helper prompt: summarise a single note for the hierarchy view."""
    system = (
        "You are a study assistant that writes 1-2 sentence summaries "
        "of academic notes. Be neutral and factual."
    )
    user = dedent(
        f"""
        Title: {title}

        Note:
        {body}

        Write a 1-2 sentence summary suitable for a sidebar preview.
        """
    ).strip()
    return system, user
