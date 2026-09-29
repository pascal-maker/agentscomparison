#!/usr/bin/env python3
"""Upload the prepared voice demo to an existing Hugging Face Space."""

from __future__ import annotations

import sys
from pathlib import Path

from huggingface_hub import CommitOperationAdd, HfApi


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} <huggingface-user-or-org/space-name>")

    repo_id = sys.argv[1]
    repo_root = Path(__file__).resolve().parents[1]
    file_map = {
        "README.md": repo_root / "energy_voice_space" / "README.md",
        "requirements.txt": repo_root / "requirements" / "energy-voice-demo.txt",
        "energy_voice_app.py": repo_root / "energy_voice_app.py",
        "energie_agent_kennisbasis_luminus_elegant_eneco.pdf": repo_root / "energie_agent_kennisbasis_luminus_elegant_eneco.pdf",
        "energyagent-karen-prototype/assets/karen-donna-style-avatar.png": repo_root / "energyagent-karen-prototype" / "assets" / "karen-donna-style-avatar.png",
        "luminus_harness/__init__.py": repo_root / "luminus_harness" / "__init__.py",
        "luminus_harness/browserbase_sources.py": repo_root / "luminus_harness" / "browserbase_sources.py",
        "luminus_harness/knowledge.py": repo_root / "luminus_harness" / "knowledge.py",
        "luminus_harness/gemma_answer.py": repo_root / "luminus_harness" / "gemma_answer.py",
        "luminus_harness/invoice_analysis.py": repo_root / "luminus_harness" / "invoice_analysis.py",
        "luminus_harness/rate_limit.py": repo_root / "luminus_harness" / "rate_limit.py",
        "luminus_harness/comparison_session.py": repo_root / "luminus_harness" / "comparison_session.py",
        "luminus_harness/provider_comparison.py": repo_root / "luminus_harness" / "provider_comparison.py",
        "luminus_harness/voice_agent.py": repo_root / "luminus_harness" / "voice_agent.py",
    }
    operations = [
        CommitOperationAdd(path_in_repo=remote, path_or_fileobj=local)
        for remote, local in file_map.items()
    ]
    result = HfApi().create_commit(
        repo_id=repo_id,
        repo_type="space",
        operations=operations,
        commit_message="Deploy EnergyAgent Karen",
    )
    print(result.commit_url)


if __name__ == "__main__":
    main()
