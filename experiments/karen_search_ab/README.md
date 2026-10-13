# Karen: publieke search A/B-proef

Dit is een geïsoleerd experiment. Niets in `energy_voice_app.py`, de Framer-component, `gemma_answer.py` of de persoonlijke aanbodvergelijking importeert deze code. De 38 vragen in `cases.json` zijn publieke, synthetische vragen zonder factuur- of persoonsgegevens. Het harnas accepteert geen vrije gebruikersvraag of geüploade PDF. Persoonlijke jaarprijzen zijn buiten scope.

**Status 13 oktober 2026:** de offline A/B-proef is geïmplementeerd. Daarnaast
is een afzonderlijke live proef met vijf Agent-antwoorden en originele
Browserbase Fetch-bronnen uitgevoerd; zie
[`docs/perplexity-agent-pilot-2026-10-13.md`](../../docs/perplexity-agent-pilot-2026-10-13.md).
Dit is geen live beoordeling van alle 38 A/B-casussen en geen bewijs voor een
zoekprovider-migratie. `KEEP_BROWSERBASE` blijft voorlopig het behoud van de
bestaande productieroute. Sleutels staan uitsluitend lokaal; de proefbestanden
met publieke broninhoud zijn Git-genegeerd.

De optionele claimcontrole op vijf casussen staat in `claim_verification.py`.
Ze gebruikt Pydantic 2 voor de structuur van handmatig afgebakende claims en
controleert vervolgens originele passages, regio, bedrag, geldigheidsperiode en
ophaaltijd. De uitvoer heet bewust nooit `VERIFIED`: een exacte passage moet
nog inhoudelijk beoordeeld worden. Zonder de lokale, Git-genegeerde
pilotresultaten is die CLI niet uitvoerbaar; de synthetische fouttests draaien
wel zonder netwerk of proefresultaten.

**Vervolg 13 oktober 2026:** de claimcontrole dekt nu elk antwoord volledig
(`pilot_claims.json`, `pilot_non_claims.json`). Er is een onafhankelijkheidsregel
voor semantische reviews (`semantic_reviews.json`), en tien extra publieke
vragen zijn beoordeeld via `agent_eval.py`, `eval_claims.json` en
`eval_non_claims.json`. Resultaat: 0 van 15 antwoorden vrijgegeven. Zie
[`docs/karen-claim-evaluation-2026-10-13.md`](../../docs/karen-claim-evaluation-2026-10-13.md).

## Bestaande route

`gemma_answer.py` gebruikt voor bepaalde publieke vragen `search_energy_pages()` uit `luminus_harness/browserbase_sources.py`. Die roept Browserbase Search aan met `site:`-termen uit een scope en `numResults=5`, filtert op vertrouwde domeinen, houdt maximaal drie kandidaten over en haalt normaal maximaal twee pagina's met Browserbase Fetch als Markdown op. Voor een gekende URL gebruikt Karen `fetch_energy_page()` zonder zoekrequest. De productieroute wordt hier niet veranderd.

De A/B-baseline gebruikt dezelfde Browserbase Search-API en `site:`-strategie, maar bewaart alle vijf ruwe rangen om `official_source@5` te kunnen beoordelen. De domeinconfiguratie is voor de proef uitgebreid met andere officiële Belgische instanties. Dit meet **discovery** en is daarom geen exacte end-to-end-herhaling van de huidige productiecode, die na filtering maximaal drie resultaten doorgeeft. De Perplexity-arm gebruikt dezelfde Nederlandse vraagquery zonder harde domeinfilter, met `country=BE`, `search_language_filter=["nl","fr"]`, vijf resultaten, `max_tokens=1500` en `max_tokens_per_page=300`. `--perplexity-domain-filter` is een aparte, expliciete sensitiviteitsproef; een domeinlijst is geen universele allowlist.

De regio, het onderwerp en een eventuele Franse vervolgquery zijn vooraf handmatig in `cases.json` vastgelegd. De proef bouwt geen nieuwe productierouter. Per provider komt er hoogstens één Franse zoekronde bij wanneer de eerste ronde geen officiële bron voor de gevraagde regio toont. Harde bovengrenzen zijn drie rondes en tien unieke pagina's per casus; de huidige dataset gebruikt maximaal twee rondes en maximaal twee officiële pagina's per provider. Dezelfde Browserbase Fetch-aanroep haalt originele officiële pagina's voor beide armen op; een gedeelde cache voorkomt dubbele fetch-kosten voor exact dezelfde URL. Fetch volgt geen redirects en niet-officiële of onveilige URL's worden geweigerd. Een gekende officiële URL kan rechtstreeks door `search_case(..., known_url=...)` en slaat search over.

De ruwe zoekranking blijft ongewijzigd voor de @3/@5-metrics. Voor het ophalen van maximaal twee pagina's krijgen officiële regelgevers en overheden voorrang; bij digitale-meter-vragen krijgt de regionale netbeheerder operationele voorrang. De resultaten van Perplexity, inclusief snippets en datumvelden, zijn alleen selectiesignalen. `evidence.verification_status` blijft `UNVERIFIED` tot iemand een **concrete, inhoudelijk ondersteunende passage op de originele pagina** beoordeelt. De bronorganisatie wordt uit het domein afgeleid als kandidaat, niet als bewijs van de claim. Zoekmetadata-datums en datums op de originele pagina staan bewust in aparte velden. Bij geen bruikbare passage is het juiste resultaat `NOT_FOUND` of `PARTIALLY_VERIFIED`, nooit een verzonnen antwoord.

## Uitvoeren

```sh
python3 -m experiments.karen_search_ab.benchmark
uv run --with pytest python -m pytest -q tests/test_karen_search_ab.py
```

Deze commando's doen geen webrequests. Voor de live, betaalde A/B-meting moeten `BROWSERBASE_API_KEY` en `PERPLEXITY_API_KEY` lokaal in de omgeving of in `.env` staan. Gebruik de bestaande `python-dotenv`-dependency; geef sleutels niet op de command line. Het harnas leest uitsluitend de statische vragen uit `cases.json`:

```sh
uv run --with python-dotenv python -m experiments.karen_search_ab.benchmark --live
```

De standaard bovengrens voor geschatte marginale kosten is $2.00 voor 38 casussen; `--max-estimated-usd` kan die grens verlagen. `--limit 5` is bruikbaar voor een kleine rookproef. De output komt lokaal in `results/` en is genegeerd door Git. De uitvoer bevat tot 10.000 tekens publieke paginainhoud per geselecteerde bron. De proef doet geen Browser Use-prijsvergelijkingen en stuurt geen PDF-gegevens naar een zoekprovider.

Het harnas maakt `latest.jsonl`, `latest-review.jsonl` en `latest-summary.json`. Vul in het reviewbestand per provider/casus `review_status: "COMPLETE"` en `finding: "VERIFIED"`, `"PARTIALLY_VERIFIED"` of `"NOT_FOUND"` in. Noteer de rangen van **correcte officiële bronnen uit de eerste ronde** in `correct_official_ranks_first_round`, of laat `[]` wanneer er geen waren. Noteer een claim en een letterlijk relevante passage uit de opgehaalde originele bron, plus de URL; beoordeel daarna `answerable`, `passage_verification`, `freshness`, `regional_correctness` en waar relevant `multilingual_recall`. Noteer publicatie- en wijzigingsdatum van de **originele pagina** wanneer zichtbaar. `unsupported_claim` mag alleen een booleaan worden wanneer ook een echte, vaste Karen-antwoordtekst in `answer_text` staat. Een lege of mislukte fetch is geen geverifieerd bewijs. Bereken na beoordeling opnieuw:

```sh
python3 -m experiments.karen_search_ab.benchmark --score-existing
```

De summary geeft officiële-bron-@3/@5, beste rang, antwoordbaarheid, passage-verificatie, actualiteit, regiocorrectheid, meertalige recall, zoekrondes, latency, geschatte kosten en (alleen bij beoordeelde antwoorden) unsupported-claim-rate. `official_domain_proxy_at_5` is nadrukkelijk **geen** officiële-bron-@5: een domeinmatch kan inhoudelijk irrelevant zijn. Niet-beoordeelde metrics blijven `null` met `n=0`. Voorbeelden waarin een provider wint of faalt moeten uit beoordeelde casussen worden geciteerd; geen automatische winnaar op basis van domeinnamen of snippets.

De kosten zijn schattingen van marginale API-tarieven na inbegrepen Browserbase-calls, niet de factuur van dit account. De huidige officiële prijstabellen vermelden Perplexity Search $5/1.000 succesvolle calls, Browserbase Search $7/1.000 na de planbundel en Browserbase Fetch Extract/Markdown $4/1.000. Het harnas telt de zoekkosten per arm en de logische fetch-kosten per arm; `actual_unique_fetch_calls` toont het gedeelde aantal betaalde fetch-aanroepen in de proef. De uiteindelijke facturatie hangt af van de accountbundel en providerresponsen.

## Beoordeling en beslissing

Adviseer `USE_PERPLEXITY_SEARCH` alleen als handmatig beoordeelde, gepaarde casussen een duidelijke verbetering laten zien in correcte officiële bronnen, originele verifieerbare passages, regio en actualiteit, zonder duidelijke verslechtering van unsupported claims, latency of kosten. Bij vergelijkbare prestaties blijft `KEEP_BROWSERBASE` de eenvoudigere keuze. `TEST_EXA` is pas zinvol als beide armen op dezelfde concrete vragen tekortschieten. Het harnas migreert Karen nooit automatisch. Browserbase Fetch en interactieve browserflows blijven apart van search.

## Officiële API-documentatie gebruikt

- [Browserbase Search](https://docs.browserbase.com/platform/search/overview): endpoint, `numResults`, resultaatvelden, 200-tekens-querylimiet.
- [Browserbase Fetch](https://docs.browserbase.com/platform/fetch/overview): Markdown, redirects, status en beperkingen voor JavaScript/PDF.
- [Browserbase prijzen](https://www.browserbase.com/pricing): planbundels en marginale Search/Fetch Extract-prijzen.
- [Perplexity Search API](https://docs.perplexity.ai/api-reference/search-post): ruwe `results[]`, `country`, talen, domeinfilter, resultaat- en contentbudgetten.
- [Perplexity prijzen](https://docs.perplexity.ai/docs/getting-started/pricing): Search-prijs per succesvolle request.
- [Exa Search API](https://exa.ai/docs/reference/search): referentie voor domeinfilter, tekst, highlights en datums; niet geïntegreerd.
- [Tavily Search](https://docs.tavily.com/documentation/api-reference/endpoint/search) en [Extract](https://docs.tavily.com/documentation/api-reference/endpoint/extract): referentie; niet toegevoegd als dependency.
