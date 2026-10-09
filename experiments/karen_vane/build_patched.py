"""Build the isolated patch using an existing checkout of the pinned Vane source."""
import argparse
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

REVISION = "348feca3e378fb4157b217724ed508dc707f853f"
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="karen-vane-build-") as temporary:
        root = Path(temporary)
        archive = root / "source.tar"
        with archive.open("wb") as output:
            subprocess.run(["git", "-C", str(args.source), "archive", REVISION], stdout=output, check=True)
        with tarfile.open(archive) as source:
            source.extractall(root, filter="data")
        archive.unlink()
        subprocess.run(["git", "apply", str(HERE / "upstream.patch")], cwd=root, check=True)
        shutil.copy(HERE / "overrides/karenGuards.ts", root / "src/lib/agents/search/karenGuards.ts")
        shutil.copy(HERE / "overrides/karenWebSearch.ts", root / "src/lib/karenWebSearch.ts")
        shutil.copy(HERE / "overrides/karenEvidence.ts", root / "src/lib/karenEvidence.ts")
        shutil.copy(HERE / "source_relations.json", root / "src/lib/karenSourceRelations.json")
        shutil.copy(HERE / "evidence.test.cjs", root)
        shutil.copy(HERE / "search_provider.test.cjs", root)
        shutil.copy(HERE / "upstream.test.cjs", root)
        shutil.copy(HERE / "Dockerfile.patched", root / "Dockerfile")
        subprocess.run(["docker", "build", "-t", "karen-vane-trial:patched", str(root)], check=True)


if __name__ == "__main__":
    main()
