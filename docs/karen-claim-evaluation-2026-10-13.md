# Karen: volledige claimdekking en tien extra publieke vragen, 13 oktober 2026

Vervolg op [`perplexity-agent-pilot-2026-10-13.md`](perplexity-agent-pilot-2026-10-13.md).
Alles blijft geïsoleerd in `experiments/karen_search_ab/`; de Framer-route,
`gemma_answer.py`, de PDF-route en de aanbodvergelijking zijn niet gewijzigd.
Er is niets gepusht of gedeployed.

## Wat er veranderd is

- **Volledige dekking.** Elk inhoudelijk woord van een antwoord moet bij een
  gestructureerde claim horen, of bij een expliciete uitzondering (`hedge`,
  `citation`, `framing`) in `*_non_claims.json`. Alleen `en`, `of`, `maar` en
  `dus` mogen los blijven. Een niet-toegewezen tekstdeel geeft
  `INCOMPLETE_COVERAGE`. Een claim zonder officiële passage krijgt een
  `evidence_note` en faalt dicht als `NO_OFFICIAL_PASSAGE`.
- **Onafhankelijke semantische review.** `semantic_reviews.json` bevat per claim
  een oordeel (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `NOT_SUPPORTED`,
  `CONTRADICTED`). Een negatief oordeel blokkeert, ongeacht wie het gaf. Een
  positief oordeel telt alleen als de reviewer niet ook de claim heeft
  opgesteld (`extracted_by`). Een review kan een gefaalde deterministische
  controle (verlopen termijn, ontbrekende passage) nooit herstellen. Het beste
  haalbare resultaat met alleen een modelreview is `NEEDS_HUMAN_SIGNOFF`.
- **Bot-challenges.** FOD Economie (beeld-CAPTCHA) en CWaPE
  (“Please wait while your request is being verified”) antwoorden Fetch met
  HTTP 200. De pilot had de FOD-CAPTCHA als “officiële pagina” bewaard.
  `retrieve_official_page` weigert zulke pagina's nu en de verifier negeert ze.
- **Volledige bronpagina's.** `claim_verification --fetch URL` bewaart een
  officiële pagina tot 200.000 tekens in het Git-genegeerde
  `results/sources/`. De pilot bewaarde slechts 10.000 tekens, vaak alleen
  navigatie.
- **Officiële domeinen toegevoegd:** `renolution.brussels` (Leefmilieu
  Brussel), `litigesenergie.brussels` (BRUGEL), `ombudsmanenergie.be`
  (Ombudsdienst voor Energie) en `consumerconnect.be` (FOD Economie).
- `agent_eval.py` vraagt per vraag één Agent-antwoord op en bewaart het ruwe
  antwoord én de status die Karens publieke route zou tonen na de
  `CURRENT_AMOUNT_UNVERIFIED`-gate.

## Resultaten

De claimextractie en de modelreview zijn van Claude (`claude-opus-5-5`). Voor
de acht oorspronkelijke pilotclaims is die review onafhankelijk; voor de 121
nieuwe claims niet, en daar tellen dus alleen de negatieve oordelen.

| Set | Antwoorden | Claims | Uitzonderingen | Geblokkeerd | Enkel nog review nodig |
| --- | ---: | ---: | ---: | ---: | ---: |
| Pilot (5 bewaarde antwoorden) | 5 | 46 | 8 | 4 | 1 (`br-04`) |
| Nieuwe vragen | 10 | 83 | 24 | 8 | 2 (`fl-05`, `wa-04`) |

Alle 129 claims vonden hun exacte passage op een officiële pagina terug, of
werden als `NO_OFFICIAL_PASSAGE` gemarkeerd. Geen enkel antwoord haalt
`NEEDS_HUMAN_SIGNOFF`. De drie niet-geblokkeerde antwoorden zijn allemaal
eenvoudige regels over ketelcontroles en -onderhoud.

Bij de nieuwe vragen deed de Agent 11 calls (één `429` voor `fl-09`, één
geslaagde herhaling). Daarnaast waren er 21 Browserbase Fetches (één HTTP 403
en twee CWaPE-interstitials). Voor het afronden van de pilotclaims kwamen er
nog 9 Fetches bij, waarvan twee een FOD-CAPTCHA opleverden.

### Waarom antwoorden geblokkeerd zijn

| Patroon | Voorbeelden |
| --- | --- |
| **Niet terug te vinden in de geciteerde bron** | `fl-06`: “aanvragen tot en met 31 december 2027” staat niet op de Vlaanderen.be-pagina. `br-05`: “bijgewerkt in juli 2025” staat niet op de Renolution-pagina. `fl-09`: “Klachtencommissie Fluvius” staat niet op de officiële stappenpagina. `fl-03`: uitbetaling “op je afrekening”. `be-12`: praktische checklist zonder bron. |
| **Regionale bron veralgemeend naar België** | `be-01` (BRUGEL), `be-03` (kmo's en vergoeding bij niet-naleving, alleen BRUGEL), `be-12` (alleen Vlaanderen.be) |
| **Verlopen of situatiegebonden bron** | `wa-05`: Waalse premie, aanvragen sloten op 30 september 2026. `be-12`: Brusselse procedure uit één faillissement in 2021, gepresenteerd als algemene regel. `wa-02`: plafond geldt volgens de bron voor de nettarieven 2020–2023. |
| **Datum verkeerd toegeschreven** | `fl-06`: wijziging van 1 maart 2026 geldt voor categorie 1–2, niet voor 3–4. `wa-05`: de datum 01/01/26 hoort bij inkomensgrenzen, niet bij de vermenigvuldigers. |
| **Premie zonder bevestigde geldigheid** | `fl-06` en `br-05`: bedragen kloppen letterlijk, maar geen pagina zegt dat aanvragen nu open zijn (`VALIDITY_UNKNOWN`). |
| **Retrieval faalt** | FOD Economie (CAPTCHA), CWaPE (twee pagina's, interstitial), Fluvius-klachtenpagina (HTTP 403), officiële PDF's (niet via Fetch) |

De huidige `CURRENT_AMOUNT_UNVERIFIED`-gate sloeg aan bij 2 van de 10 nieuwe
antwoorden (`fl-06`, `br-05`). Die twee blokkeert de verifier ook. **Zes
andere geblokkeerde antwoorden zou de publieke Agent-route wel tonen**
(`fl-03`, `fl-09`, `br-08`, `wa-02`, `be-03`, `be-12`). Hun fouten zitten niet
in bedragen, maar in onbevestigde procedures, regionale veralgemening en
verouderde bronnen.

## Externe review van het pilotpakket

Er kwam een tweede, onafhankelijke review van de 46 pilotclaims binnen. De
links daarin dragen `utm_source=chatgpt.com` en sommige bedragen zijn tegen
een commerciële site gecontroleerd. Daarom staat die review in
`semantic_reviews.json` als `external-review-2026-10-13` met
`reviewer_type: "model"`, niet als menselijke review.

- **Gecorrigeerd op basis van die review.** De Fluvius-FAQ bevestigt de
  minimumbijdrage van 2,5 kW voor elke klant, ook met een digitale meter, en
  het tarief in euro per kW. De twee betreffende claims verwijzen nu naar die
  passage. Mijn oordelen over “voorschot is een raming” en “verrekening op de
  afrekening” zijn herzien naar `SUPPORTED`.
- **Nieuwe fout.** “Ik kon de Q4-bedragen daar niet rechtstreeks verifiëren”
  is geen hedge maar een onjuiste claim: de CREG-pagina linkt beide Q4-PDF's.
  Beide reviewers geven `CONTRADICTED`.
- **`wa-05`.** De SPW-nieuwspagina van 24 september 2026 bevestigt de sluiting
  op 30 september 2026, met overgangsregels voor oudere projecten tot
  30 september 2027.
- **Nog oneens.** Deze punten blokkeren nog, omdat een negatief oordeel van
  één reviewer volstaat. Een mens moet beslissen:
  - “doorgaans in overleg”: BRUGEL zegt “bepaalde leveranciers”;
  - “ongeacht netbeheerder”: de externe review raadt zelf aan dit te schrappen;
  - “excl. btw” zonder de andere uitsluitingen (energiebijdrage, accijns);
  - “CREG is de officiële bron voor de regeling”.

Resultaat pilot: `fl-01` en `br-04` zijn `NEEDS_HUMAN_SIGNOFF`; `wa-05`,
`be-01` en `be-08` blijven `BLOCKED`.

### Tweede externe review: de tien nieuwe vragen

Elke nieuwe bron die de reviewer noemde, is eerst zelf via Fetch opgehaald
en gecontroleerd.

- **`br-05` is fout als actueel antwoord.** Leefmilieu Brussel (14 september
  2026): “Ces primes sont actuellement suspendues.” be.brussels: “Op dit moment
  kunnen er geen premie-aanvragen met eindfactuur 2025 of 2026 worden
  ingediend.” **De J4-pagina en de homepage van renolution.brussels vermelden
  dat niet.** Een controle per pagina op termijnen kan dit dus nooit
  opvangen. `be.brussels` is toegevoegd aan de officiële domeinen.
- **Bevestigd en verwerkt.** Er bestaat een Fluvius-Klachtencommissie
  (Vlaanderen.be-organisatiepagina). De Ombudsdienst eist voorafgaande stappen
  per brief, e-mail of fax. Mijn oordelen zijn aangepast.
- **Deels bevestigd.** De termijn van 31 december 2027 (`fl-06`) bestaat, maar
  staat bij inkomenscategorie 1–2 en andere investeerders. Dezelfde pagina zegt:
  “Voor eigenaar-bewoners uit inkomenscategorie 3 en 4 verandert er niets”, en
  het antwoord gaat net over categorie 3–4. Dat bevestigt ook dat
  “Sinds 1 maart 2026” verkeerd is toegeschreven.
- **Niet overgenomen.** Volgens de reviewer gebruikt `wa-02` het verouderde
  percentage van 37,76 %. Het antwoord noemt echter geen percentage; dat cijfer
  kwam uit mijn bewijsquote. Die verwijst nu naar ORES (40,26 %). Het negatieve
  oordeel op de oude quote is daarom niet opgenomen.
- **Niet te verifiëren.** De CWaPE-bronnen (tariefmethodologie 2026–2029,
  vervangingslevering) gaven opnieuw een bot-challenge. De oordelen van de
  reviewer staan erin, maar de claims blijven zonder eigen passage.

Resultaat nieuwe vragen: `fl-05`, `br-08` en `wa-04` zijn
`NEEDS_HUMAN_SIGNOFF`; de andere zeven blijven `BLOCKED`.

**Architectuurconclusie.** Beide reviews bevestigen hetzelfde: retrieval vindt
de inhoud meestal wel, maar de geldigheid in de tijd faalt. Een premie of
tarief mag pas als actueel worden gebracht na een aparte statuscontrole per
regeling (`current_status`, `valid_from`, `valid_until`, `superseded_by`). Die
controle moet gevoed worden door door mensen bijgehouden statusbronnen per
regeling, zoals de nieuwspagina van Leefmilieu Brussel of SPW. De
productpagina zelf volstaat niet.

## Besluit

**Geen productie- of Framer-migratie voorstellen.** Houd `KEEP_BROWSERBASE`
en de bestaande Framer-route. Onderbouwing: 0 van de 15 antwoorden is
vrijgegeven, 12 zijn geblokkeerd op inhoud, en de bestaande gate laat 6
geblokkeerde antwoorden door.

Wat er eerst nodig is, in deze volgorde:

1. **Menselijke review** van de drie open antwoorden en van alle
   `PARTIALLY_SUPPORTED`-oordelen. Gebruik daarvoor het reviewpakket (zie
   hieronder). Pas met een menselijke `SUPPORTED` voor elke claim kan een
   antwoord `HUMAN_REVIEWED_SUPPORTED` worden.
2. **Gate voor niet-monetaire claims.** Bijvoorbeeld: alleen antwoorden waarvan
   elke zin naar een passage op een gegeven officiële pagina verwijst, of
   standaard alleen de officiële links tonen.
3. **Retrieval voor CWaPE en FOD Economie.** Deze bronnen zijn essentieel voor
   Wallonië en het sociaal tarief, maar blokkeren automatische Fetch.
   Daarnaast is ondersteuning voor officiële PDF's nodig.
4. **Geautomatiseerde claimextractie** als derde, onafhankelijke stap. Elk
   van deze 15 antwoorden vroeg 3 tot 15 handmatige claims; dat schaalt niet.

## Reproduceren (zonder nieuwe betaalde calls)

```sh
PYTHONPATH=. python -m experiments.karen_search_ab.claim_verification \
  --review-packet experiments/karen_search_ab/results/review-packet-2026-10-13.md
PYTHONPATH=. python -m experiments.karen_search_ab.claim_verification \
  --run agent-eval-2026-10-13.json --run agent-eval-2026-10-13-fl09-retry.json \
  --claims eval_claims.json --non-claims eval_non_claims.json \
  --review-packet experiments/karen_search_ab/results/review-packet-eval-2026-10-13.md
uv run --with pytest --with pydantic --with python-dotenv python -m pytest -q \
  tests/test_karen_claim_verification.py tests/test_karen_claim_audit.py tests/test_karen_search_ab.py
```

Beide reviewpakketten (Markdown-checklists met antwoord, claim, bron en passage
per regel) staan Git-genegeerd in `experiments/karen_search_ab/results/`. Wie
review doet, voegt per claim een item met `reviewer_type: "human"` en de eigen
naam als `reviewer` toe aan `semantic_reviews.json`. Zonder de lokale
resultaten slaan de twee snapshottests over; de synthetische tests draaien
altijd.

`agent_eval.py --live` vereist de nog niet gecommitte module
`luminus_harness/perplexity_agent.py` en doet betaalde calls.

## Update 2026-10-13: validity-gate (aanbeveling #2) geïmplementeerd

De eerdere `VALIDITY_UNKNOWN`-status was een regex over de geciteerde
productpagina (`past_deadlines`/`_periods`): die ziet geen opschorting of
deadline die elders op de site staat. Daarom is `regime_status.json`
toegevoegd: een apart, door een mens bijgehouden record per regeling met
`current_status` (`open`/`suspended`/`closed`), `valid_from`, `valid_until`
en `superseded_by`. Een claim verwijst ernaar via een nieuw optioneel
`scheme_id`-veld; zonder `scheme_id` blijft de oude heuristiek ongewijzigd
van toepassing.

Toegepast op de drie regelingen die vorige keer op `VALIDITY_UNKNOWN` of
`EXPIRED_DEADLINE` bleven steken:

- `wallonia_prime_habitation_heat_pump_2025_2026` — `closed` (30/09/2026).
  Resultaat ongewijzigd (`EXPIRED_DEADLINE`); dit werkte al via de oude
  regex, nu ook expliciet getrackt.
- `flanders_mijn_verbouwpremie_heat_pump` — `open`, `valid_until` 31/12/2027.
  **13 van de 15 `fl-06`-claims gaan van `VALIDITY_UNKNOWN` naar
  `HUMAN_REVIEW_SUPPORTED`.** De case blijft `BLOCKED`, maar nu om een
  eerlijke, controleerbare reden: 2 claims hebben een nog openstaand
  meningsverschil met een eerder model-oordeel
  (`fl06_since_march_2026_type_and_income`, `fl06_apply_until_end_2027`),
  niet omdat het systeem de geldigheid niet kon vaststellen.
- `brussels_renolution_j4_heat_pump` — `suspended`. **12 van de 13
  `br-05`-claims gaan van `VALIDITY_UNKNOWN` naar de nieuwe, precieze status
  `SCHEME_SUSPENDED`.** Case blijft terecht `BLOCKED`.

Geen van de 15 cases flipte naar een hogere eindverdict — dat was ook niet
het doel. Het doel was dat een blokkade zijn juiste, specifieke reden krijgt
in plaats van het generieke "onbekend", zodat een volgende reviewronde weet
waar die wél (reviewer-meningsverschil) en niet (een harde schorsing) iets
aan kan veranderen.

Nieuwe statussen: `SCHEME_SUSPENDED`, `SCHEME_NOT_YET_OPEN`. Zie
`experiments/karen_search_ab/regime_status.json` voor het schema en
`tests/test_karen_claim_verification.py` voor de dekking.
