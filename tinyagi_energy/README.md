# Luminus Energy Support on TinyAGI

[TinyAGI](../tinyagi) is a multi-agent, multi-channel, 24/7 AI assistant. Unlike the
single-script demos in this repo, a TinyAGI agent is **configured**, not run as one
file: each agent has a workspace `AGENTS.md` (its system prompt) and a set of skills
under `.agents/skills/`. This folder is a drop-in Luminus support configuration.

## Contents

```
tinyagi_energy/
├── AGENTS.md                              # team layout + approved system prompt
└── skills/
    └── luminus-energy/
        ├── SKILL.md                       # billing / advice / appointment skill
        └── scripts/energy.sh              # simulated Luminus billing backend
```

## Try the skill script directly

No model or daemon required to see the tool layer:

```bash
chmod +x tinyagi_energy/skills/luminus-energy/scripts/energy.sh

tinyagi_energy/skills/luminus-energy/scripts/energy.sh billing LUM-1001
tinyagi_energy/skills/luminus-energy/scripts/energy.sh advice LUM-1002 heating
tinyagi_energy/skills/luminus-energy/scripts/energy.sh appointment LUM-1003 "meter replacement" 2026-07-15
```

## Run it as a TinyAGI agent

1. Install and start TinyAGI (Node 18+, Claude Code or Codex CLI for the provider):

   ```bash
   cd ../tinyagi
   npm install && npm run build
   npm start
   ```

2. Copy this config into your agent workspace:
   - put `AGENTS.md`'s approved system prompt into the agent's workspace `AGENTS.md`
   - copy `skills/luminus-energy/` into the workspace `.agents/skills/`

3. Message the agent (Discord / Telegram / WhatsApp / TinyOffice portal):

   > Hi, my account is LUM-1002 and my bill jumped this month — why, and how do I lower it?

The `support` agent asks for the account id, calls the `luminus-energy` skill for billing
and advice, and hands appointment requests to `scheduler` for human approval.
