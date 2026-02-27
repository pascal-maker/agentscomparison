"""
Smart Discovery — Streamlit UI
================================
Multiple sources (Notion URLs + pasted content) → one Sweetspot PowerPoint.

Run from project root:
    streamlit run streamlit_app.py
"""

import sys
import os
import logging
from pathlib import Path

# Ensure project root is on the path and all relative paths resolve correctly
PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

import streamlit as st

# ============================================================================
# Page config (must be first Streamlit call)
# ============================================================================
st.set_page_config(
    page_title="Smart Discovery",
    layout="wide",
)

# ============================================================================
# Session state — source list
# ============================================================================
if "sources" not in st.session_state:
    st.session_state.sources = [{"type": "url", "label": "Source 1", "value": ""}]


def add_source():
    n = len(st.session_state.sources) + 1
    st.session_state.sources.append({"type": "url", "label": f"Source {n}", "value": ""})


def remove_source(i: int):
    st.session_state.sources.pop(i)


# ============================================================================
# Header
# ============================================================================
st.title("Smart Discovery")
st.caption("Notion → PowerPoint | Sweetspot")
st.divider()

# ============================================================================
# Mode + customer name
# ============================================================================
customer_name = "Client"
presentation_title = ""
must_include_raw = ""
slide_min = 8
slide_max = 30
per_section_max = 4

col_mode, col_name = st.columns([3, 1])

with col_mode:
    mode = st.radio(
        "Mode",
        ["Smart Discovery", "Simple Mode"],
        horizontal=True,
        help=(
            "**Smart Discovery** — Claude analyzes all sources, grounds every bullet "
            "to evidence, and flags gaps as Open Questions.\n\n"
            "**Simple Mode** — Converts structure directly to slides. No LLM."
        ),
    )

with col_name:
    if mode == "Smart Discovery":
        customer_name = st.text_input("Customer name", value="Client")
    else:
        presentation_title = st.text_input("Presentation title", placeholder="Optional")

st.divider()

# ============================================================================
# Sources
# ============================================================================
st.subheader("Sources")
st.caption("Add as many sources as you need — interviews, workshops, desk research, …")

for i, source in enumerate(st.session_state.sources):
    col_type, col_label, col_remove = st.columns([1.2, 3, 0.4])

    with col_type:
        source["type"] = st.selectbox(
            "Type",
            ["url", "paste"],
            index=0 if source["type"] == "url" else 1,
            key=f"type_{i}",
            label_visibility="collapsed",
        )

    with col_label:
        source["label"] = st.text_input(
            "Label",
            value=source["label"],
            key=f"label_{i}",
            label_visibility="collapsed",
            placeholder="Label (e.g. Interview CEO, Workshop output, Desk research)",
        )

    with col_remove:
        if len(st.session_state.sources) > 1:
            st.button("✕", key=f"remove_{i}", on_click=remove_source, args=(i,))

    if source["type"] == "url":
        source["value"] = st.text_input(
            "Notion URL",
            value=source["value"],
            key=f"value_{i}",
            placeholder="https://www.notion.so/your-page-id",
            label_visibility="collapsed",
        )
    else:
        source["value"] = st.text_area(
            "Content",
            value=source["value"],
            key=f"value_{i}",
            placeholder="Paste content from Notion, Word, email — anything works.",
            height=150,
            label_visibility="collapsed",
        )

st.button("+ Add source", on_click=add_source)

# ============================================================================
# Advanced options (Smart Discovery only)
# ============================================================================
if mode == "Smart Discovery":
    with st.expander("Advanced options"):
        must_include_raw = st.text_input(
            "Required sections (comma-separated)",
            placeholder="Executive Summary, Key Findings, Recommendations",
            help="These section names are enforced in the output.",
        )
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            slide_min = st.number_input("Min slides", value=8, min_value=1, max_value=50)
        with col_b:
            slide_max = st.number_input("Max slides", value=30, min_value=1, max_value=100)
        with col_c:
            per_section_max = st.number_input(
                "Max slides per section", value=4, min_value=1, max_value=20
            )

# ============================================================================
# Run button
# ============================================================================
st.divider()
has_input = any(s["value"].strip() for s in st.session_state.sources)
run = st.button("Generate PowerPoint", type="primary", disabled=not has_input)

if not has_input:
    st.caption("Fill in at least one source to get started.")

# ============================================================================
# Pipeline execution
# ============================================================================
if run and has_input:
    log_placeholder = st.empty()
    log_lines: list[str] = []

    class StreamlitLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            msg = self.format(record)
            log_lines.append(msg)
            log_placeholder.code("\n".join(log_lines[-25:]), language=None)

    handler = StreamlitLogHandler()
    handler.setFormatter(logging.Formatter("%(name)s | %(message)s"))

    logger_names = [
        "SmartDiscovery", "NotionToPPTX", "NotionReader",
        "ContentAnalyzer", "Revisor",
    ]
    for name in logger_names:
        logging.getLogger(name).addHandler(handler)

    result: dict = {}

    with st.spinner("Running pipeline…"):
        try:
            # Split sources into URLs and pasted content
            notion_urls, raw_contents, source_labels = [], [], []
            simple_url, simple_content = None, None

            for source in st.session_state.sources:
                val = source["value"].strip()
                if not val:
                    continue
                label = source["label"].strip() or f"Source {len(source_labels) + 1}"
                if source["type"] == "url":
                    notion_urls.append(val)
                else:
                    raw_contents.append(val)
                source_labels.append(label)

            if mode == "Smart Discovery":
                from teams.smart_discovery import smart_discover
                from shared.evidence import CustomerConfig

                must_include = (
                    [s.strip() for s in must_include_raw.split(",") if s.strip()]
                    if must_include_raw
                    else ["Executive Summary", "Key Findings", "Recommendations"]
                )
                config = CustomerConfig(
                    name=customer_name,
                    must_include=must_include,
                    slide_budget={
                        "min": slide_min,
                        "max": slide_max,
                        "per_section_max": per_section_max,
                    },
                )
                result = smart_discover(
                    notion_urls=notion_urls or None,
                    raw_contents=raw_contents or None,
                    source_labels=source_labels or None,
                    customer_name=customer_name,
                    config=config,
                )

            else:
                from teams.notion_to_pptx import notion_to_pptx

                # Simple mode: use first source only
                first = next(
                    (s for s in st.session_state.sources if s["value"].strip()), None
                )
                result = notion_to_pptx(
                    notion_url=first["value"].strip() if first and first["type"] == "url" else None,
                    raw_content=first["value"].strip() if first and first["type"] == "paste" else None,
                    title=presentation_title.strip() or None,
                )

        except Exception as exc:
            result = {"success": False, "error": str(exc)}

    for name in logger_names:
        logging.getLogger(name).removeHandler(handler)

    log_placeholder.empty()

    # ========================================================================
    # Results
    # ========================================================================
    if result.get("success"):
        st.success("Done!")

        if mode == "Smart Discovery":
            validation = result.get("validation") or {}
            grounded = validation.get("grounded_bullets", 0)
            total = validation.get("total_bullets", 1)
            pct = f"{int(grounded / total * 100)}%" if total else "—"

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Sources read", len(result.get("sources_read", [])))
            m2.metric("Evidence items", result.get("evidence_count", 0))
            m3.metric("Sections", len(result.get("sections", [])))
            m4.metric("Grounding", pct)

            # Sources summary
            sources_read = result.get("sources_read", [])
            if sources_read:
                with st.expander(f"Sources read ({len(sources_read)})"):
                    for s in sources_read:
                        url_part = f" — {s['url']}" if s.get("url") else ""
                        st.write(f"**{s['label']}**: {s['title']}{url_part}")
        else:
            m1, m2 = st.columns(2)
            m1.metric("Sections", len(result.get("sections", [])))
            m2.metric("Slides", result.get("slide_count", 0))

        # Download PowerPoint
        pptx_path = result.get("powerpoint_path")
        if pptx_path and Path(pptx_path).exists():
            pptx_bytes = Path(pptx_path).read_bytes()
            st.download_button(
                label="Download PowerPoint (.pptx)",
                data=pptx_bytes,
                file_name=Path(pptx_path).name,
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )

        # Sections list
        if result.get("sections"):
            with st.expander("Sections generated"):
                for i, section in enumerate(result["sections"], 1):
                    st.write(f"{i}. {section}")

        # Markdown report (Smart Discovery only)
        if mode == "Smart Discovery":
            md_path = result.get("markdown_path")
            if md_path and Path(md_path).exists():
                md_content = Path(md_path).read_text()
                with st.expander("Markdown report"):
                    st.download_button(
                        label="Download Markdown (.md)",
                        data=md_content,
                        file_name=Path(md_path).name,
                        mime="text/markdown",
                    )
                    st.markdown(md_content)

    else:
        error = result.get("error", "Unknown error — check logs above.")
        st.error(f"Pipeline failed: {error}")
