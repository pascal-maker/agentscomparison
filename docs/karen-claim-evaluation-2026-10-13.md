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
