#!/usr/bin/env bash
# Luminus energy-support data script for TinyAGI.
# Simulates the billing / metering backend. In production, replace the lookups
# below with real Luminus API calls.
#
# Usage:
#   energy.sh billing     <customerId>
#   energy.sh advice      <customerId> [heating|appliances|general]
#   energy.sh appointment <customerId> <reason> <YYYY-MM-DD>
set -euo pipefail

lookup() {
  # echoes "name|plan|last_bill" or empty if unknown
  case "$1" in
    LUM-1001) echo "Sofie|Comfy Fixed|142.50" ;;
    LUM-1002) echo "Marc|Dynamic|208.90" ;;
    LUM-1003) echo "Amira|Solar Buyback|76.20" ;;
    *) echo "" ;;
  esac
}

cmd="${1:-}"
cid="${2:-}"
row="$(lookup "$cid")"

if [[ -z "$row" && "$cmd" != "help" ]]; then
  echo "No Luminus account found for '${cid}'." >&2
  exit 1
fi
IFS='|' read -r name plan bill <<<"$row"

case "$cmd" in
  billing)
    echo "Account ${cid} (${name}, ${plan}): last bill €${bill}."
    echo "Increase vs. average is driven by higher evening peak-hour usage and a seasonal rate adjustment this quarter."
    ;;
  advice)
    focus="${3:-general}"
    echo "Tailored energy-saving advice for ${name} (${plan} plan), focus=${focus}:"
    case "$focus" in
      heating)
        echo "- Lower the thermostat by 1°C to cut heating ~6%."
        echo "- Use a smart thermostat schedule so heating is off when nobody is home." ;;
      appliances)
        echo "- Shift dishwasher/laundry to off-peak (after 22:00) — especially on Dynamic."
        echo "- Switch standby devices off at the wall to remove always-on load." ;;
      *)
        echo "- Shift heavy appliances to off-peak hours (after 22:00)."
        echo "- Lower the thermostat by 1°C (~6% heating savings)."
        echo "- Kill standby load on always-on devices (~8% of usage)." ;;
    esac
    ;;
  appointment)
    reason="${3:-inspection}"
    date="${4:-}"
    [[ -z "$date" ]] && { echo "appointment requires a date (YYYY-MM-DD)." >&2; exit 1; }
    ref="APPT-${cid}-${date//-/}"
    echo "PROPOSED appointment for ${name} on ${date} (${reason}). Reference ${ref}."
    echo "ACTION REQUIRED: ask the user to approve before this is booked."
    ;;
  help|*)
    echo "Usage: energy.sh {billing|advice|appointment} <customerId> [args...]" ;;
esac
