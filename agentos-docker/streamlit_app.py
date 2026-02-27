"""
Smart Discovery — Streamlit UI
================================
Paste a Notion URL → get a Sweetspot PowerPoint.

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
# Header
# ============================================================================
st.title("Smart Discovery")
st.caption("Notion → PowerPoint | Sweetspot")
st.divider()

# ============================================================================
# Mode selector
# ============================================================================
mode = st.radio(
    "Mode",
    ["Smart Discovery", "Simple Mode"],
    horizontal=True,
    help=(
        "**Smart Discovery** — Claude analyzes your Notion page, grounds every bullet "
        "to an evidence item, and flags gaps as Open Questions.\n\n"
        "**Simple Mode** — Converts the Notion structure directly to slides. No LLM, no grounding."
    ),
)

st.divider()

# ============================================================================
# Inputs — initialize all variables with defaults first
# ============================================================================
customer_name = "Client"
presentation_title = ""
must_include_raw = ""
slide_min = 8
slide_max = 30
per_section_max = 4

col_url, col_name = st.columns([3, 1])

with col_url:
    input_mode = st.radio("Input", ["Notion URL", "Paste content"], horizontal=True)

with col_name:
    if mode == "Smart Discovery":
        customer_name = st.text_input("Customer name", value="Client")
    else:
        presentation_title = st.text_input(
            "Presentation title",
            placeholder="Optional",
        )

notion_url = ""
raw_content_input = ""

if input_mode == "Notion URL":
    notion_url = st.text_input(
        "Notion URL",
        placeholder="https://www.notion.so/your-page-id",
    )
else:
    raw_content_input = st.text_area(
        "Paste your content here",
        placeholder="Copy and paste from Notion, Word, email — anything works.",
        height=250,
    )

# Advanced options (Smart Discovery only)
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
has_input = bool(notion_url.strip() or raw_content_input.strip())
run = st.button("Generate PowerPoint", type="primary", disabled=not has_input)

if not has_input:
    st.caption("Add a Notion URL or paste content to get started.")

# ============================================================================
# Pipeline execution
# ============================================================================
if run and notion_url.strip():
    log_placeholder = st.empty()
    log_lines: list[str] = []

    # Custom logging handler that streams into the UI
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
            url = notion_url.strip() or None
            content = raw_content_input.strip() or None

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
                    notion_url=url,
                    raw_content=content,
                    customer_name=customer_name,
                    config=config,
                )

            else:
                from teams.notion_to_pptx import notion_to_pptx

                result = notion_to_pptx(
                    notion_url=url,
                    raw_content=content,
                    title=presentation_title.strip() or None,
                )

        except Exception as exc:
            result = {"success": False, "error": str(exc)}

    # Remove handlers
    for name in logger_names:
        logging.getLogger(name).removeHandler(handler)

    log_placeholder.empty()

    # ========================================================================
    # Results
    # ========================================================================
    if result.get("success"):
        st.success("Done!")

        # Metrics row
        if mode == "Smart Discovery":
            validation = result.get("validation") or {}
            grounded = validation.get("grounded_bullets", 0)
            total = validation.get("total_bullets", 1)
            pct = f"{int(grounded / total * 100)}%" if total else "—"

            m1, m2, m3 = st.columns(3)
            m1.metric("Evidence items", result.get("evidence_count", 0))
            m2.metric("Sections", len(result.get("sections", [])))
            m3.metric("Grounding", pct)
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
