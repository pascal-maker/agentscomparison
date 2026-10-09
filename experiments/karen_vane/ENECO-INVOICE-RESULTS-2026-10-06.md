# Eneco-voorschot versus afrekening — lokale verticale proef

## Resultaat

De ene gekozen vraag geeft nu een kort Nederlands antwoord met een officiële
Eneco-bron. De antwoordtekst is een vast sjabloon van vier zinnen. Voor elke
zin moet een specifieke passage op Eneco's eigen afrekeningpagina aanwezig zijn;
anders toont de Python-adapter slechts bronmateriaal ter beoordeling.

De laatst geslaagde live vraag duurde **19,32 seconden** en gaf
`answer_with_sources`, `evidence_status=passage_checked` en één bron:
`https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie/`.
De log meldde drie Tavily-aanroepen van één credit, dus **drie credits**.

## Wat veranderde

- Voor alleen deze Eneco-factuurvraag bewaart Vane passende `eneco.be`-pagina's
  vóór het samenvoegen op embeddinggelijkenis. In de geslaagde run bleven de
  afrekeningpagina en de voorschotpagina over.
- Vane beëindigt dit ene vraagtype na de zoekstap. De eerdere live proef hield
  beide pagina's over, maar de lokale schrijver overschreed daarna de
  90-secondenlimiet. Die proef kostte twee Tavily-credits en gaf geen antwoord.
- De adapter haalt de gevonden officiële afrekeningpagina direct op en vergelijkt
  de benodigde passages. Hij toont de vier vaste zinnen pas als elke controle
  slaagt. De bronlink is dezelfde pagina; het door Vane geschreven proza wordt
  niet gebruikt.
- Na de geslaagde live run kreeg elke zin een eigen `[1]`-verwijzing. Deze kleine
  presentatieaanpassing is met lokale tests geverifieerd, zonder extra live run.

## Controle

- **14 Node-tests** tijdens de lokale Docker-build; Next.js-compilatie en
  TypeScript-controle geslaagd.
- **21 Python-tests** voor de adapter, bronregels, afwijkende of ontbrekende
  pagina-inhoud en deze antwoordroute geslaagd.
- De openbare Eneco-pagina gaf HTTP 200 en bevatte alle vereiste passages.
- Ruwe probe: `output/karen-vane/eneco-invoice-ready-2026-10-06.jsonl`
  (gitignored). De directe mislukte start direct na containerherstart staat in
  `eneco-invoice-2026-10-06.jsonl`; dat was een verbindingsfout vóór zoeken en
  gebruikte geen credits.

Dit toont één geslaagd vraagtype, geen algemene betrouwbare energie-assistent.
De pagina kan later veranderen; dan valt de route terug op bronpassages.
Andere vragen blijven bij de bestaande `sources_for_review`-uitkomst. Deze
proef is niet naar Framer of de gehoste Karen gedeployd. Een gebruikersvraag
kan nog altijd meerdere Tavily-credits kosten doordat Vane meerdere zoektermen
maakt.
