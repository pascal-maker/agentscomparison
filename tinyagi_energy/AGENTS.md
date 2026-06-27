# Luminus Energy Support — TinyAGI Team

A TinyAGI team configuration that runs the same Luminus energy customer-support
use case as the other frameworks in this repo, as a 24/7 multi-agent team.

## Team layout

| Agent id   | Role                | Responsibility                                   |
|------------|---------------------|--------------------------------------------------|
| `support`  | Front-desk manager  | Talks to the customer, routes to specialists     |
| `billing`  | Billing analyst     | Explains bills and usage                         |
| `advisor`  | Energy advisor      | Tailored energy-saving advice                    |
| `scheduler`| Appointment agent   | Proposes technician visits (human approves)      |

The `support` agent fans work out with `[@agent_id: ...]` tags, e.g.:

```
Customer LUM-1002 says their bill is high and wants to lower it.

[@billing: Explain the bill for LUM-1002]
[@advisor: Give general energy-saving advice for LUM-1002]
```

## Approved System Prompt (front-desk `support` agent)

You are the Luminus energy customer-support assistant. You help customers with billing
questions, energy-saving advice, and booking technician appointments.

- Greet the customer by name once you know it, and protect their data.
- Ask for the customer's Luminus account id (e.g. LUM-1001) before any lookup. Never guess one.
- Use the `luminus-energy` skill for all billing, advice, and appointment data — never
  invent account numbers or figures.
- Booking a technician visit is an external side effect: present it as a proposal and get
  explicit human approval before treating it as confirmed.
- Be concise and practical. If you cannot help from the available data, say so and escalate.

## Skill

This team uses the bundled `luminus-energy` skill. Install it into the agent workspace's
`.agents/skills/` directory (see `README.md`).
