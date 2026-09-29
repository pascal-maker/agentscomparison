#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <huggingface-user-or-org/space-name>" >&2
  exit 2
fi

space_id="$1"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
dotenv_path="$repo_root/.env"

if [[ ! -f "$dotenv_path" ]]; then
  echo "Missing $dotenv_path. Copy .env.example to .env and add the required secrets." >&2
  exit 1
fi

hf auth whoami >/dev/null
hf repo create "$space_id" \
  --repo-type space \
  --space-sdk gradio \
  --flavor zero-a10g \
  --public \
  --exist-ok \
  --secrets OPENAI_API_KEY \
  --secrets GEMINI_API_KEY \
  --secrets BROWSERBASE_API_KEY \
  --secrets BROWSER_USE_API_KEY \
  --secrets HF_TOKEN \
  --secrets-file "$dotenv_path"

hf_executable="$(command -v hf)"
hf_python="$(head -n 1 "$hf_executable")"
hf_python="${hf_python#\#!}"
"$hf_python" "$repo_root/scripts/upload_energy_voice_space.py" "$space_id"

echo "Deployed: https://huggingface.co/spaces/$space_id"
