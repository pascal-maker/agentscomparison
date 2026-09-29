---
title: EnergyAgent Karen
emoji: 🎙️
colorFrom: green
colorTo: yellow
sdk: gradio
sdk_version: 5.50.0
python_version: 3.12
app_file: energy_voice_app.py
pinned: false
---

# EnergyAgent Karen

A Dutch voice assistant for Belgian household energy questions. Karen retrieves
relevant passages from the bundled energy FAQ PDF and optional visitor uploads.
For current supplier help pages, Karen can use Browserbase Search and Fetch
against a fixed allowlist of trusted energy and regulator websites. There are no
sample customer accounts or simulated bills.

## Required Space secrets

- `OPENAI_API_KEY` (for the existing Gradio voice baseline)
- `GEMINI_API_KEY` (for Gemma 4 answers from Framer)
- `BROWSERBASE_API_KEY` (enables live retrieval from the curated official help
  and regulator pages; the FAQ retrieval works without it)
- `BROWSER_USE_API_KEY` (enables regional offer comparisons through V-test,
  BruSim, or CompaCWaPE). `BROWSER_USE_MAX_COST_USD` defaults to `1.00` per
  lookup; incomplete requests do not start a lookup.

The public API is rate-limited to 20 requests per client IP per minute, with a
bounded in-process client map. The public FAQ answer endpoint uses the hosted
Gemma API; visitors are told not to include personal information in those
questions. Do not use this free-tier route for personal bills.

When a visitor uploads a PDF, the file is sent to this Hugging Face backend.
The backend extracts selectable text and creates a rule-based first read without
calling Google or OpenAI. Retrieved PDF chunks stay in a bounded server-side
session for at most 60 minutes and can be deleted from the UI. Text follow-ups
retrieve and display matching page excerpts locally. The Gradio OpenAI voice
route is blocked while an uploaded PDF is active, so bill text is not sent to
that provider. Scanned PDFs without selectable text are not analyzed. This is
server-side local processing, not processing on the visitor's device.

## Files uploaded to the Space

- `energy_voice_app.py`
- `energyagent-karen-prototype/assets/karen-donna-style-avatar.png` Karen's avatar
- `luminus_harness/` voice agent, PDF retrieval, and source browser
- `requirements/energy-voice-demo.txt` as `requirements.txt`
- this file as the Space root `README.md`

For public FAQ voice turns, the Space records audio in the browser and sends it
to the existing OpenAI Agents voice baseline after the visitor presses the
button. Karen speaks a short acknowledgment while source lookup and answer run.
Uploaded PDF content is not passed to that voice route.
TariefCheck is linked separately for sustainable-work quotes; Karen does not
submit it or send visitor contact details.

## Framer answer API

- The Gradio UI is served at `/ui/` (the Space root redirects there).
- `POST /api/upload` accepts multipart field `file` with a PDF, performs local
  extraction/analysis, and returns an opaque `session_id` plus page-linked
  evidence. Upload limit: 15 MB, 30 pages, 120,000 extracted characters.
- `POST /api/answer` accepts `{ "question": "...", "session_id": "..." }`.
  With a session ID it returns local retrieval excerpts without calling a model;
  without one, explicit offer comparisons run before the public FAQ/Gemma and
  CREG routes. Other questions keep their existing behavior. A successful live
  CREG fetch is distinguished from a failed or unavailable fetch.
- Offer comparisons collect the stated region, four-digit postcode, one energy
  type, and annual kWh consumption. Karen asks for missing or ambiguous values;
  she does not infer annual use from monthly figures. Collecting responses return
  an opaque `comparison_session_id`, separate from the PDF `session_id`, which
  typed and recognized voice follow-ups send with `question`.
- Only structured comparison inputs remain in bounded process memory (64
  sessions, 60-minute fixed expiry), with requested field identifiers and an
  in-flight flag. The comparator can request meter type, meter technology,
  annual day/night consumption, and prosumer status. Karen collects those
  explicit answers before retrying; invalid or missing answers do not start
  another lookup. Unsupported requirements or repeated requests for already
  supplied fields close the comparison with an official link. Inputs are
  discarded after a terminal result, expiry, or cancellation. Terminal responses clear the comparison
  token. `DELETE /api/comparison-session/{comparison_session_id}` removes a
  pending comparison early. Multiple workers would require session affinity or
  shared temporary storage.
- Successful comparisons return up to three displayed annual costs, check time,
  and source links. Missing comparator inputs and failures return no confirmed
  prices. Comparison requests with a PDF session ask the visitor to clear the
  PDF first; invoice text never goes to Browser Use.
- `DELETE /api/session/{session_id}` deletes the uploaded-text session early;
  otherwise it expires after 60 minutes. The in-memory session store is bounded.
- `GET /api/health` reports API availability, model, and local-only PDF handling.
- Set `FRAMER_ALLOWED_ORIGINS` to a comma-separated list of exact published
  custom origins if Framer uses a domain outside `framer.app` or
  `framer.website`.
- Gemma API calls use `GEMINI_API_KEY`; keep it in Space Secrets, never in the
  Framer component. Use only public FAQ material with the Google free-tier API.
- The Framer component sends typed questions and PDF uploads. Uploaded PDF
  follow-ups use the local retrieval route. Public FAQ questions use hosted
  Gemma; the Gradio recording path is a separate OpenAI voice baseline.
