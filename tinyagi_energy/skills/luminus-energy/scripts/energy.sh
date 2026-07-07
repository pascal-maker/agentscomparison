#!/usr/bin/env bash
# Luminus energy-support data script for TinyAGI.
# Delegates to the shared repository harness so TinyAGI uses the same customer
# fixtures and scenario text as the Python demos.
#
# Usage:
#   energy.sh billing     <customerId>
#   energy.sh advice      <customerId> [heating|appliances|general]
#   energy.sh appointment <customerId> <reason> <YYYY-MM-DD>
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../../.." && pwd)"
python_bin="${PYTHON:-python}"

cmd="${1:-help}"

case "$cmd" in
  billing)
    [[ $# -ge 2 ]] || { echo "billing requires a customerId." >&2; exit 1; }
    (cd "$repo_root" && "$python_bin" -m luminus_harness billing "$2")
    ;;
  advice)
    [[ $# -ge 2 ]] || { echo "advice requires a customerId." >&2; exit 1; }
    (cd "$repo_root" && "$python_bin" -m luminus_harness advice "$2" "${3:-general}")
    ;;
  appointment)
    [[ $# -ge 4 ]] || { echo "appointment requires <customerId> <reason> <YYYY-MM-DD>." >&2; exit 1; }
    (cd "$repo_root" && "$python_bin" -m luminus_harness appointment "$2" "$3" "$4")
    ;;
  help|*)
    echo "Usage: energy.sh {billing|advice|appointment} <customerId> [args...]"
    ;;
esac
