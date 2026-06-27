---
name: luminus-energy
description: "Handle Luminus energy customer-support requests — explain a customer's bill, give tailored energy-saving advice, and propose a technician appointment for approval. Use when: a customer asks about their bill or charges, asks how to lower their consumption, or needs a meter replacement / inspection visit. Triggers: 'my bill', 'why is my bill high', 'save energy', 'lower my bill', 'book a technician', 'meter replacement', 'appointment', or any message with a Luminus account id like LUM-1001."
---

# Luminus Energy Support

Provide Luminus energy customer support: billing explanations, energy-saving advice,
and technician appointment requests. All data comes from `scripts/energy.sh` — never
invent account numbers or figures.

Always ask for the customer's Luminus account id (e.g. `LUM-1001`) before looking
anything up, and greet the customer by name once known.

## Explain a bill

```bash
<skill_dir>/scripts/energy.sh billing LUM-1001
```

Relay the explanation in plain language and offer next steps.

## Give energy-saving advice

```bash
# focus is optional: heating | appliances | general (default)
<skill_dir>/scripts/energy.sh advice LUM-1001 heating
```

## Propose a technician appointment (human-in-the-loop)

Booking a technician visit is an external side effect, so it is **never** auto-confirmed.
Produce a proposal, then ask the user to approve before treating it as booked.

```bash
<skill_dir>/scripts/energy.sh appointment LUM-1001 "smart meter replacement" 2026-07-15
```

The script returns a `PROPOSED` appointment with `ACTION REQUIRED`. Send the proposal to
the customer (or escalate to a human teammate) and only confirm once approval is given.

## Multi-agent handoff

In a Luminus support team you can fan work out to specialist teammates:

- `[@billing: Explain the bill for LUM-1002]`
- `[@advisor: Give heating advice for LUM-1002]`
- `[@scheduler: Propose a meter-replacement visit for LUM-1002 on 2026-07-20]`
