# Karen: vijf publieke energievraagstukken, 13 oktober 2026

Dit is een **kleine, handmatig beoordeelde proef**, geen productie-migratie of
algemene providerbenchmark. De vijf vragen komen uit
[`experiments/karen_search_ab/cases.json`](../experiments/karen_search_ab/cases.json).
De Agent kreeg de natuurlijke Nederlandstalige vraag. De Browserbase-baseline
zocht met de vooraf opgestelde, regionale query uit die testset. De latencies
zijn daarom niet rechtstreeks vergelijkbaar als eind-tot-eind-antwoorden.
Er is geen factuur, klantgegeven of aanbodvergelijking doorgestuurd.

| Casus | Agent-antwoord beoordeeld | Oorspronkelijke bron en reden |
| --- | --- | --- |
| `fl-01` capaciteitstarief | **Onderbouwd voor de kernpunten.** | [Fluvius](https://www.fluvius.be/nl/factuur-en-tarieven/capaciteitstarief/gezinnen-en-kleine-ondernemingen/op-mijn-factuur) bevestigt kwartierpiek, maandpiek, gemiddelde over twaalf maanden en het onderscheid met een klassieke meter. [Fluvius Prepaid](https://prepaid.fluvius.be/mijn-factuur/wat-kost-energie-bij-fluvius/capaciteitstarief) vermeldt de minimumpiek van 2,5 kW. |
| `br-04` gasketelcontrole | **Onderbouwd.** | [Leefmilieu Brussel](https://leefmilieu.brussels/verwarmingsketel) vermeldt een EPB-controle om de twee jaar voor aardgas, na ingrepen aan het verbrandingsgedeelte en uitvoering door erkende technici. |
| `wa-05` warmtepomppremie | **Onvoldoende actueel.** | De [officiële Waalse premiepagina](https://energie.wallonie.be/home/soutiens-financiers/particuliers/primes-pour-la-renovation/prime-habitation/prime-pour-son-habitation-a-partir-du-14-fevrier-2025.html) noemt de basisbedragen van €600 en €280 voor de regeling 2025–2026, maar zegt ook dat aanvragen uiterlijk 30 september 2026 ingediend moesten zijn. Het Agent-antwoord noemt bedragen en voorwaarden zonder deze verlopen termijn; op 13 oktober is dat misleidend als aanvraagadvies. |
| `be-01` voorschot wijzigen | **Gedeeltelijk.** | [Vlaanderen.be](https://www.vlaanderen.be/bouwen-wonen-en-energie/elektriciteit-en-aardgas/factuur-voor-elektriciteit-en-aardgas/energiefactuur-voor-elektriciteit-of-aardgas) ondersteunt het contact en de online aanpassing in Vlaanderen. [BRUGEL](https://brugel.brussels/nl_BE/themes/consumenten-7/mijn-factuur-begrijpen-13) ondersteunt de Brusselse passage over overleg en een gemotiveerde weigering. De algemene Belgische vraag krijgt geen Waalse of volledig nationale afbakening. Browserbase vond ook een [CREG-pagina](https://www.creg.be/nl/a-z-index/voorschotfactuur), maar een officiële URL alleen bewijst de ontbrekende claim niet. |
| `be-08` sociaal tarief | **Bedragen achteraf bevestigd; bronverwijzing zwak.** | De officiële [CREG-elektriciteitstabel](https://www.creg.be/sites/default/files/assets/Tarifs/Social/E-TSS-NL-2026-Q4.pdf) bevat 20,957–25,331 c€/kWh excl. btw voor de vermelde metertypes; de [CREG-gastabel](https://www.creg.be/sites/default/files/assets/Tarifs/Social/G-TSS-NL-2026-Q4.pdf) bevat 5,738 c€/kWh excl. btw. Het Agent-antwoord verwees voor de bedragen naar een commerciële blog en zei dat het ze niet rechtstreeks bij CREG kon bevestigen. De officiële [CREG-overzichtspagina](https://www.creg.be/nl/consumenten/prijzen-en-tarieven/sociaal-tarief/sociaal-tarief-voor-energie) linkt naar beide Q4-PDF’s. |

De Agent deed **5 requests**, gemiddeld 8,4 seconden (6,1–10,8 s). De
Browserbase Search-baseline deed **5 zoekrequests**, gemiddeld 1,1 seconde,
zonder fouten; alle vijf hadden een officieel domein in de top drie. Dat is
slechts een *domeinproxy*: bij `wa-05` waren de hoogste treffers oude of
technische documenten en gaven ze geen actueel aanvraagadvies. Voor de
handmatige broncontrole werden daarnaast 14 Browserbase Fetch-aanroepen
gedaan, waaronder vier voor de twee CREG-PDF’s (eerst controleren, daarna de
uitgelezen tekst bewaren). De precieze Agent-kosten zijn in deze proef niet
vastgelegd; API-call-aantallen zijn geen accountfactuur.

De proefuitvoer staat lokaal en Git-negeerd in
`experiments/karen_search_ab/results/agent-pilot-2026-10-13.json`,
`browserbase-five-case-baseline.json` en de twee
`creg-q4-2026-*.txt`-bestanden. De vijf Agent-antwoorden werden vastgelegd
**vóór** de correctie die expliciete links uit antwoordtekst voorrang geeft
boven losse zoekkandidaten. Die codecorrectie verandert de historische
uitvoer niet; er is geen tweede betaalde Agent-run gedaan.

**Besluit:** houd de bestaande Framer-route. Een Agent-citaat, antwoordlink of
officieel domein is nog geen verificatie van een claim. Voor automatische
inzet zijn ten minste nodig: ophalen van de daadwerkelijk gebruikte originele
pagina, ondersteuning voor officiële PDF’s, een voldoende lange relevante
passage (niet alleen de eerste 10.000 tekens navigatie), controle op geldende
termijnen en een fail-closed pad voor onbevestigde actuele bedragen of premies.

Aanvullende controle: `python -m experiments.karen_search_ab.claim_audit`
gebruikt de bewaarde publieke antwoorden en originele pagina's, zonder Agent-
of zoekrequest. Eén afzonderlijke Browserbase Fetch van de volledige officiële
Waalse pagina is opgeslagen in het Git-genegeerde
`results/wa-05-original-full.json`-bestand. De audit vond daarop zowel de
genoemde €600 en €280 als de verlopen deadline **30 september 2026**. De twee
officiële CREG-PDF-teksten bevatten de genoemde cent/kWh-bedragen, maar de audit
noemt dat slechts `TEXT_MATCH_ONLY`: een letterlijke cijfermatch is geen volledige
verificatie van periode, meter, btw en toepasbaarheid. De optionele publieke
Agent-route schermt zulke actuele bedragen inmiddels af met
`CURRENT_AMOUNT_UNVERIFIED`; Framer blijft op de bestaande route.

## Claimcontrole op de vijf bewaarde antwoorden

De geïsoleerde controle in
[`experiments/karen_search_ab/claim_verification.py`](../experiments/karen_search_ab/claim_verification.py)
neemt acht **handmatig afgebakende** claims uit de vijf Agent-antwoorden. Hun
gestructureerde velden staan in `pilot_claims.json`. Pydantic controleert de
vorm en dat een genoemd bedrag ook in het antwoordfragment staat; het bewijst
geen inhoudelijke juistheid. De controle eist vervolgens de exacte officiële
URL, de juiste regionale of federale bevoegdheid, een concrete passage op die
originele pagina, het bedrag met eenheid in die passage en bij tarieven een
toepasselijke periode. Voor premieclaims wordt een expliciete verstreken
aanvraagtermijn herkend. Conflicterende bedragen en oude ophaaltijd falen dicht.

| Casus | Uitkomst van de gekozen claims |
| --- | --- |
| `fl-01` | 1 teruggevonden Fluvius-passage; inhoudelijke controle blijft nodig. |
| `br-04` | 1 teruggevonden passage van Leefmilieu Brussel; inhoudelijke controle blijft nodig. |
| `wa-05` | 2 bedragen op de officiële pagina, maar beide claims afgewezen door de deadline van 30 september 2026. |
| `be-01` | 1 teruggevonden Vlaanderen-passage over contact bij een betwist voorschot. Dit dekt niet automatisch de bredere Belgische vraag. |
| `be-08` | 3 bedragen in de officiële CREG-PDF-teksten met de periode oktober–december 2026; de juiste meter, btw en doelgroep vragen nog inhoudelijke beoordeling. |

Dit zijn **8 geselecteerde claims, geen volledige dekking van alle zinnen** in
de antwoorden. De status `PASSAGE_MATCH_NEEDS_REVIEW` betekent uitdrukkelijk
geen `VERIFIED`: dezelfde cijfers of woorden kunnen in een ander verband op een
pagina staan. De originele proefbestanden en de twee extra volledige Fetches
zijn lokaal en Git-genegeerd. Zonder die bestanden wordt de optionele
snapshot-test overgeslagen; de synthetische foutgevallen blijven gewoon testen.

Run zonder betaalde calls:

```sh
PYTHONPATH=. python -m experiments.karen_search_ab.claim_verification
PYTHONPATH=. pytest -q tests/test_karen_claim_verification.py
```

De publieke Agent-route en Framer gebruiken deze proefcontrole nog niet. Eerst
zijn volledige claimdekking, een onafhankelijke inhoudelijke beoordeling en
een gecontroleerde evaluatie op meer dan vijf vragen nodig.

**Vervolg:** volledige dekking (46 claims), de reviewregel en tien extra vragen
staan in [`karen-claim-evaluation-2026-10-13.md`](karen-claim-evaluation-2026-10-13.md).
Let op: de FOD Economie-pagina in de pilotuitvoer hierboven bleek een CAPTCHA
te zijn, geen originele bron.
