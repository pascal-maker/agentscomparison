# Framer Code Component

## Stateful offer comparisons — 28 September 2026

The component now sends a separate `comparison_session_id` for typed and
recognized voice follow-ups. `/api/answer` handles explicit offer comparisons
before Gemma or CREG retrieval. Karen asks for a stated gewest, four-digit
postcode, one energy type, and positive annual consumption in kWh. An inline
kWh figure without a yearly period is not assumed to be annual; a numeric reply
to the year-consumption prompt is accepted. She never derives a region from a
postcode or an annual total from monthly figures or day/night splits.

The initial request can be `{"question":"Vergelijk energieaanbiedingen"}`.
A collecting response includes `comparison_status: "collecting"`,
`comparison_session_id`, and `required_information`. Follow-up requests include
that opaque comparison token alongside `question`. Results return up to three
displayed annual costs, a check time, and source cards; terminal responses set
`comparison_session_id` to `null`. Service failures contain no confirmed prices and show the official comparator
under links to consult yourself. Supported additional requirements (meter type,
meter technology, annual day/night kWh, prosumer status) keep the token active
and ask for explicit answers. Missing or invalid answers do not retry the lookup.
Unknown requirements or repeated requests for already supplied fields close the
comparison with the official link.

Only structured comparison inputs, requested field identifiers, an in-flight
flag, and an expiry timestamp are stored
in bounded server memory (64 unfinished sessions per process). The deadline is
60 minutes from creation and does not renew between turns. Timers discard
expired inputs even without another request. Duplicate requests during a lookup do not start another lookup. Inputs are
removed after a terminal result, on cancellation (`annuleer`), or via
`DELETE /api/comparison-session/{comparison_session_id}`. Multiple backend
workers would need session affinity or shared temporary storage.

Comparison inputs are sent to the existing Browser Use comparator with its
existing spend cap and regional mappings. A PDF session blocks this route and
asks the visitor to clear the PDF; it never contributes invoice text or inferred
consumption. Uploading a PDF clears the component's comparison token and requests
deletion of that state. The microphone stays available between comparison turns
and stays disabled for PDFs. Browser speech synthesis reads the exact returned
answer, including prompts and comparison results.

Validation uses a mocked comparator in `tests/test_karen_offer_comparison.py`;
the React DOM test in `tests/test_karen_component.cjs` checks source links,
typed/voice continuity, exact spoken text, token reset, and PDF isolation. Run
the latter with temporary `react@18`, `react-dom@18`, `jsdom@26`, and `esbuild`
dependencies on `NODE_PATH`. No live paid comparison is part of these tests.
The Hugging Face upload script includes the new session module and existing
comparator so backend deployments include both. Framer remains unpublished.

The comparison backend was deployed to the existing Space on 28 September 2026
at commit
[`83c9954e91299b24a73ac63177d8a8b46b52e111`](https://huggingface.co/spaces/pascal-maker/belgian-energy-voice-assistant/commit/83c9954e91299b24a73ac63177d8a8b46b52e111).
The Space is running that revision on its existing hardware. The Browser Use
secret was already present; credentials and the existing cost cap were retained.
Live checks passed for health, multi-turn input collection, session isolation,
monthly-consumption rejection, cancellation, synthetic PDF upload and local
follow-up, and the PDF comparison block. The actual answer response allows the
existing Framer Preview origin. All test sessions were deleted.

Reproduce the live smoke check with
`python scripts/check_karen_comparison_deployment.py https://pascal-maker-belgian-energy-voice-assistant.hf.space`.
It submits only incomplete comparison inputs and a generated synthetic PDF;
it never completes a paid comparator request. Actual offer retrieval and live
microphone recognition remain unverified.

The comparison component was saved to the existing Framer code file through
the Framer CLI and type-checked without diagnostics. The `/live-demo` Preview
rendered a clearly labelled mock comparison with its official source card;
the real backend URL was restored afterwards. Exact voice-answer playback was
verified with a mocked browser speech API in the React DOM test, without
recording microphone audio. The earlier local-only sync notes below describe
previous attempts; this latest component is now synced to Framer.

`EnergyAgentConversation.tsx` is the interactive Energy co-pilot component used on the **Live Demo** page of the Framer project **Predictable Evidence**. The project contains a separate homepage; keep that page unchanged.

## Framer project

The component is stored as a Framer Code File and its source is duplicated in this repository. Framer does not sync these files automatically; after changing the local component, copy the full source into the project's `EnergyAgentConversation.tsx` code file, confirm the save indicator, then review `/live-demo` in Preview. The Karen logo is embedded as a small WebP data URI so Framer does not need a separate asset upload.

Set **Backend URL** to the Hugging Face backend's public HTTPS URL ending in `/api/answer`. The component derives `/api/upload` and `/api/session` from that endpoint. Leave it empty only for a simulated layout preview. Provider keys remain on the backend; no key belongs in Framer.

## Expected API contract

Set **Backend URL** to the Space URL ending in `/api/answer`. For a typed
question without an uploaded PDF, the component sends JSON:

```json
{ "question": "Waarom verschilt mijn voorschot van mijn jaarafrekening?" }
```

After upload, the component receives an opaque session identifier and includes
it with each follow-up question. Those PDF follow-ups use local retrieval; the
uploaded text is not sent to Google or OpenAI. The PDF itself is sent to the
Hugging Face backend, where its extracted text is retained in bounded in-memory
session storage for up to 60 minutes or until deleted. Do not describe this as
on-device processing.

The component expects JSON shaped like:

```json
{
  "answer": "Antwoord van Karen",
  "processing": "Optioneel: local-only (op de backend), hosted-public-knowledge of verified-public-sources",
  "live_source_status": "Optioneel: checked, failed of not-needed",
  "sources": [
    {
      "title": "Bronnaam",
      "detail": "PDF · pagina 4",
      "url": "https://…",
      "excerpt": "Optioneel bronfragment"
    }
  ],
  "suggested_sources": [
    {
      "title": "Officiële pagina om zelf te raadplegen",
      "url": "https://…",
      "detail": "Geen verifieerbare passage opgehaald; niet als bewijs gebruikt"
    }
  ]
}
```

The local component displays `suggested_sources` separately from evidence. A
missing backend now supports only the fixed advance-versus-settlement sample;
other questions show a connection message rather than the unrelated sample
answer. These changes are not synced to Framer. Its fresh full-page Preview has
the backend URL configured, while the embedded code Preview previously showed
a simulated answer. Recheck both after manually syncing through an allowed path.

Retry on 2026-09-28, explicitly requested by the user: Browser Use again rejected
opening `http://127.0.0.1:4174/source-transfer.html`. This time the stated reason
was a saved user permission setting blocking the localhost origin. No alternate
transfer path was attempted and Framer source remains unchanged. The temporary
transfer server was stopped after the rejection.

The Space backend provides `POST /api/upload`, `POST /api/answer`, and
`DELETE /api/session/{session_id}`. Upload analysis and follow-up are local
extraction/retrieval with cited PDF page excerpts. Without a PDF session,
`/api/answer` uses Gemma 4 over the bundled public knowledge base and may fetch a
current CREG source through Browserbase. The component's microphone uses browser
Web Speech recognition and sends the resulting public question to the same
`/api/answer` endpoint as typed input. The browser speech service processes the
audio; browser speech synthesis reads Karen's returned answer text. Recognition
stops at the end of the turn and submits automatically. This is a push-to-talk
baseline, not Gemini Live or GPT-Live; it does not provide realtime barge-in or
compare those hosted voice providers. A PDF session disables the microphone and
text-only PDF follow-up stays on the Karen backend. The UI warns visitors to use
public questions and avoid personal invoice details via voice. Typing remains
available if browser speech recognition is unavailable.

For a recognized public voice question, the local component speaks a short
“Ik zoek het even op.” acknowledgement while the API call runs, then speaks the
exact answer returned by the backend. It does not stream partial answers. This
acknowledgement change has only been compiled locally; it is not yet synced to
Framer or verified in the Preview.

## Voice diagnosis update — 28 September 2026

The local component now distinguishes browser speech errors such as `no-speech`,
`not-allowed`, `audio-capture`, and `network`, and displays when audio or speech
is detected. The live Framer project has not received this diagnostic update:
the browser security policy blocked opening the temporary localhost source
transfer page and reported that access was declined. No alternate transfer path
was attempted. The current Framer preview therefore still needs the existing
generic voice error until the code can be synced through an allowed route.


## Review repairs — 29 September 2026

The console tool and `/api/answer` now share the structured comparison collector.
Supported comparator follow-ups are forwarded explicitly; false prosumer status
and zero day/night use are preserved. Unknown requirements and repeated requests
for supplied fields close safely. Concurrent calls cannot duplicate a lookup;
expiry and PDF/cancellation deletion cannot resurrect an in-flight session.
The console checks each current transcription before calling Runner, allows
short answers only for a pending comparison, and refuses unrelated questions
in Dutch while permitting supplier comparisons.

The implementation and its dependencies/assets are staged together. Verification
used an isolated `git archive HEAD` plus the staged binary patch, without `.env`
or API credentials: `openai/demo.py --help`, all 117 Python tests, 92 backend
checks with the Space's pinned Agents SDK, and the React component test passed.
The console uses its separate `requirements/openai-agents.txt` environment; the
Space SDK pin is for the backend, not the console's existing approval demos.

The connected Framer component type-checked without diagnostics. Its privacy
text now covers explicit meter/prosumer inputs. Actual Framer preview rendered
a labelled mock comparison and its official source card; the original backend
setting was restored and the mock result cleared. Voice continuity and exact
spoken answers were checked with mocked browser speech APIs. No paid comparator
call or live microphone recognition was tested. Framer remains unpublished, and
these backend review repairs have not been deployed to the Space.
