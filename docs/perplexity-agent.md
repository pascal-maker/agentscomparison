# Optionele Perplexity Agent API voor publieke energievraag

Karen heeft een afzonderlijke `POST /api/public-web-answer`-route voor een korte,
algemene Belgische energievraag. Deze route gebruikt de officiële Perplexity
Python-SDK en `web_search` om een Nederlandstalig antwoord met bron-URLs te
maken. De bestaande `/api/answer`-route, Framer-component, PDF-verwerking,
aanbodvergelijking en de geïsoleerde Search API-benchmark veranderen hierdoor niet.

Zet `PERPLEXITY_API_KEY` in de **procesomgeving van de Karen-server**. De
server leest voor deze integratie geen sleutel uit een andere projectmap. Zet
de sleutel niet in Framer of in een request. Een voorbeeldverzoek:

```sh
curl -X POST http://localhost:7860/api/public-web-answer \
  -H 'Content-Type: application/json' \
  -d '{"question":"Wat is het capaciteitstarief in Vlaanderen?"}'
```

Het antwoord bevat `answer`, `sources`, `processing` en `evidence_status`.
`AGENT_CITED_UNVERIFIED` betekent dat de Agent API machineleesbare bronverwijzingen
gaf; `ANSWER_LINKS_UNVERIFIED` betekent dat het antwoord zelf bronlinks bevat;
`SEARCH_CANDIDATES_UNVERIFIED` betekent dat de API alleen zoekresultaten gaf.
In alle gevallen heeft Karen de passages op
de oorspronkelijke websites nog niet onafhankelijk gecontroleerd. Zonder
compleet antwoord en bron retourneert de route `NOT_FOUND`. De route accepteert
geen PDF- of vergelijkingssessies en weigert
herkenbare persoonlijke factuur- en contractgegevens. Deze eenvoudige controle
is geen volledige PII-detector: gebruik de route uitsluitend voor algemene
publieke vragen. Er is nog geen automatische routing vanuit Framer.

Voor concrete bedragen en premieclaims geeft de route nu
`CURRENT_AMOUNT_UNVERIFIED` en houdt ze de Agent-tekst achter. Alleen links
naar herkende officiële instanties blijven zichtbaar. Dit is een conservatieve
veiligheidsgrens, geen automatische bronverificatie: ook een letterlijk bedrag
op een officiële pagina kan bij een andere periode of situatie horen. De
geïsoleerde proefcontrole in `experiments/karen_search_ab/claim_audit.py`
vergelijkt de opgeslagen antwoorden met originele broninhoud en herkent een
expliciet verstreken aanvraagtermijn. Ze verandert de Framer-route niet.

De live smoke-test op 13 oktober 2026 leverde met `openai/gpt-6-luna`,
`reasoning: none`, `max_steps: 3` en beperkte zoekbudgetten een complete
response met zoekresultaten en antwoordtekst. De eerdere proef met
`openai/gpt-5.6-sol` en een lage output-tokenlimiet was `incomplete`.

Officiële API-documentatie: [index](https://docs.perplexity.ai/llms.txt),
[Agent quickstart](https://docs.perplexity.ai/docs/agent-api/quickstart),
[tools](https://docs.perplexity.ai/docs/agent-api/tools/overview),
[web search](https://docs.perplexity.ai/docs/agent-api/tools/web-search),
[output control](https://docs.perplexity.ai/docs/agent-api/output-control),
[endpoint](https://docs.perplexity.ai/api-reference/agent-post),
[SDK](https://docs.perplexity.ai/docs/sdk/overview),
[pricing](https://docs.perplexity.ai/docs/getting-started/pricing).
