// Run with NODE_PATH pointing to temporary react@18, react-dom@18, jsdom@26 and esbuild dependencies.
// No browser speech service, backend, or paid comparator is contacted.
const assert = require("node:assert/strict")
const path = require("node:path")
const vm = require("node:vm")
const { JSDOM } = require("jsdom")
const { buildSync } = require("esbuild")

const dom = new JSDOM('<div id="root"></div>', { url: "https://preview.example/" })
Object.assign(globalThis, {
    window: dom.window, document: dom.window.document,
    HTMLElement: dom.window.HTMLElement, FormData: dom.window.FormData,
    IS_REACT_ACT_ENVIRONMENT: true,
})
Object.defineProperty(globalThis, "navigator", { configurable: true, value: dom.window.navigator })
const React = require("react")
const { act } = React
const { createRoot } = require("react-dom/client")
const spoken = []
globalThis.SpeechSynthesisUtterance = class { constructor(text) { this.text = text } }
window.speechSynthesis = { getVoices: () => [{ lang: "nl-BE" }], cancel() {}, speak: utterance => spoken.push(utterance.text) }
let recognizer
window.SpeechRecognition = class {
    constructor() { recognizer = this }
    start() {}
    stop() { this.onend?.() }
}
const source = require("node:fs").readFileSync(path.join(__dirname, "../energyagent-karen-prototype/EnergyAgentConversation.tsx"), "utf8")
const compiled = buildSync({
    stdin: { contents: source, loader: "tsx", resolveDir: path.join(__dirname, "../energyagent-karen-prototype") },
    bundle: false, write: false, format: "cjs", jsx: "automatic",
}).outputFiles[0].text
const componentModule = { exports: {} }
vm.runInNewContext(compiled, {
    module: componentModule, exports: componentModule.exports,
    require: name => name === "framer" ? { addPropertyControls() {}, ControlType: { String: "string" } } : require(name),
    window, console, URL, fetch: (...args) => globalThis.fetch(...args), FormData,
    setTimeout, SpeechSynthesisUtterance,
})
const Component = componentModule.exports.default
const root = createRoot(document.querySelector("#root"))
const requests = []
const responses = []
globalThis.fetch = async (url, options) => {
    requests.push({ url, method: options.method, body: typeof options.body === "string" ? JSON.parse(options.body) : options.body })
    if (options.method === "DELETE") return { ok: true, json: async () => ({ deleted: true }) }
    assert.ok(responses.length, "Unexpected request")
    const reply = responses.shift()
    return { ok: true, json: async () => reply }
}
const token = "structured-comparison-session"
const collecting = { answer: "In welk gewest woon je?", comparison_status: "collecting", comparison_session_id: token, sources: [] }
const success = {
    answer: "V-test toont dit aanbod.\n\n1. Voorbeeld · Variabel: € 1.234,56 per jaar. Gecontroleerd op 28-09-2026 om 14:00 CEST.",
    comparison_status: "success", comparison_session_id: null, live_source_status: "checked",
    sources: [{ title: "Voorbeeld · Variabel", url: "https://www.vlaamsenutsregulator.be/results", detail: "V-test · gecontroleerd 28-09-2026" }],
}
const mic = () => document.querySelector(".ea-mic")
async function typed(question) {
    const input = document.querySelector(".ea-input")
    await act(async () => {
        Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set.call(input, question)
        input.dispatchEvent(new window.Event("input", { bubbles: true }))
    })
    await act(async () => document.querySelector('[aria-label="Verstuur vraag"]').click())
}
async function voice(question) {
    assert.equal(mic().disabled, false, "Comparison must keep voice available between turns")
    await act(async () => mic().click())
    await act(async () => {
        recognizer.onresult({ results: [[{ transcript: question }]] })
        recognizer.onend?.()
    })
}
async function main() {
    await act(async () => root.render(React.createElement(Component, { apiEndpoint: "https://backend.example/api/answer", sampleQuestion: "sample" })))
    responses.push(collecting)
    await typed("Vergelijk energieaanbiedingen")
    assert.deepEqual(requests.at(-1).body, { question: "Vergelijk energieaanbiedingen" })
    assert.equal(mic().disabled, false)
    responses.push({ ...collecting, answer: "Wat is je postcode?" })
    await voice("Vlaanderen")
    assert.deepEqual(requests.at(-1).body, { question: "Vlaanderen", comparison_session_id: token })
    assert.equal(spoken.at(-1), "Wat is je postcode?")
    responses.push({ ...collecting, answer: "Ben je prosument? Antwoord ja of nee.", required_information: ["is_prosumer"] })
    await voice("Postcode 9000, elektriciteit, jaarlijks 3500 kWh")
    assert.equal(requests.at(-1).body.comparison_session_id, token)
    assert.equal(spoken.at(-1), "Ben je prosument? Antwoord ja of nee.")
    assert.equal(mic().disabled, false)
    responses.push(success)
    await voice("nee")
    assert.equal(requests.at(-1).body.comparison_session_id, token)
    assert.equal(document.querySelector(".ea-answer").textContent, success.answer)
    assert.equal(document.querySelector(".ea-rail a").href, success.sources[0].url)
    assert.equal(spoken.at(-1), success.answer, "Speak the exact verified answer")
    assert.equal(mic().disabled, false)
    responses.push({ answer: "FAQ antwoord", comparison_session_id: null })
    await typed("Waarom verschilt mijn voorschot?")
    assert.equal(requests.at(-1).body.comparison_session_id, undefined)
    responses.push(collecting)
    await typed("Vergelijk gas")
    responses.push({ answer: "Lokale PDF-analyse", session_id: "separate-pdf-session", filename: "bill.pdf", processing: "local-only" })
    await act(async () => {
        const input = document.querySelector('input[type="file"]')
        Object.defineProperty(input, "files", { configurable: true, value: [new window.File(["synthetic"], "bill.pdf", { type: "application/pdf" })] })
        input.dispatchEvent(new window.Event("change", { bubbles: true }))
    })
    assert.ok(requests.some(r => r.method === "DELETE" && r.url.endsWith(`/api/comparison-session/${token}`)))
    assert.equal(mic().disabled, true, "PDF session must disable external voice")
    responses.push({ answer: "Verwijder eerst je PDF", comparison_status: "pdf-blocked", comparison_session_id: null, processing: "local-only" })
    await typed("Vergelijk gas")
    assert.deepEqual(requests.at(-1).body, { question: "Vergelijk gas", session_id: "separate-pdf-session" })
    assert.notEqual(spoken.at(-1), "Verwijder eerst je PDF")
    await act(async () => [...document.querySelectorAll("button")].find(button => button.textContent === "Verwijder").click())
    assert.equal(mic().disabled, false)
    await act(async () => root.unmount())
    dom.window.close()
    console.log("Karen component: typed/voice session continuity, source cards, exact spoken answer, terminal reset and PDF isolation passed.")
}
main().catch(error => { console.error(error); process.exitCode = 1; dom.window.close() })
