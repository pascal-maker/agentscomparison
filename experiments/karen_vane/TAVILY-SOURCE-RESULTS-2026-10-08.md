# Tavily-bronselectie voor Karen — lokale proef, 8 oktober 2026

## Uitkomst

De drie openbare regressievragen leveren nu passende bronkandidaten via de
lokale Vane/Tavily-route. Alleen de bestaande Eneco-factuurvraag levert een
inhoudelijk antwoord met passagecontrole. De Waalse gasketelvraag en de
algemene Eneco-vraag blijven `sources_for_review`, met
`evidence_status=unverified`; gevonden URL's bewijzen de modeltekst niet.

| Vraag | Laatste live tijd | Tavily-credits in containerlog | Uitkomst |
| --- | ---: | ---: | --- |
| Onderhoud versus periodieke gasketelcontrole in Wallonië | 32,07 s | 1 | Eén officiële [Waalse energiepagina](https://energie.wallonie.be/home/au-quotidien/dans-lindustrie/conseils-techniques/chauffage-ventilation-et-climatisation/vous-avez-dit-entretien-des-chaudieres-et-des-bruleurs.html); `sources_for_review` |
| Eneco voorschotfactuur versus jaarafrekening | 16,53 s | 1 | Eén officiële [Eneco-afrekeningpagina](https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie/); `answer_with_sources`, `passage_checked` |
| What is Eneco? | 33,06 s | 1 | Vijf `eneco.nl`-pagina's, geen Singaporese naamgenoot; `sources_for_review` |

Ruwe lokale resultaten staan in `output/karen-vane/wallonia-boiler-filter-2026-10-08.jsonl`,
`eneco-search-regression-2026-10-08.jsonl` en
`eneco-invoice-search-fix-2026-10-08.jsonl` (allemaal gitignored).
De geslaagde laatste runs melden samen drie credits. Eerdere diagnose- en
mislukte regressieruns meldden nog vijf credits; samen zijn **acht credits
expliciet gerapporteerd** in deze werkronde. Een onderbroken directe proef gaf
geen resultaat terug; eventuele accountboeking daarvan is niet gecontroleerd.

## Oorzaak en wijziging

De oorspronkelijke Vane-zoektermen lieten soms het gevraagde gewest weg.
Een breed `wallonie.be`-filter liet officiële maar irrelevante pagina's over
huurherstellingen en mazouttanks toe. Een streng trefwoordfilter verwierp
vervolgens de juiste ketelpagina omdat Tavily's korte fragment geen `gaz`
bevatte, terwijl een schoorsteenpagina toevallig alle trefwoorden noemde.

De proef houdt bij expliciete gewest- of Eneco-vragen de oorspronkelijke
vraag als zoekanker. De herkenbare Waalse gasketelvergelijking krijgt één
Franse zoekterm en `energie.wallonie.be` als Tavily-domeingrens. Voor die
vraag moeten titel of URL over een ketel gaan en moet het fragment zowel
onderhoud als controle behandelen. De juiste officiële ketelpagina mag als
**kandidaat** blijven wanneer het korte fragment `gaz` niet vermeldt.
Afzonderlijke officiële URL's blijven vóór embedding-deduplicatie behouden.
De Python-adapter herhaalt de broncontrole na Vane.

De eerste Eneco-regressie liet zien dat een Tavily-domeinbeperking bij de
factuurvraag juist een tariefpagina naar voren schoof. Voor die specifieke
vraag zoekt Tavily daarom weer zonder domeinbeperking; de bronfilter laat
daarna alleen eigen Belgische Eneco-URL's over afrekening of
voorschotfactuur toe. De eerder passage-gecontroleerde antwoordroute bleef
intact en gebruikte bij de laatste live run één in plaats van drie credits.

## Validatie en grenzen

De gepinde Docker-build slaagde met 21 Node-tests, een Next.js-build en
TypeScript-controle. De adapter en bronregels slaagden met 24 Python-tests.
De tests omvatten de oorspronkelijke Brusselse passage voor Wallonië,
de Singaporese Eneco-naamgenoot, het verlies van verschillende officiële
URL's bij embedding-deduplicatie, de afgewezen gasnet-/schoorsteenpagina's
en de korte Tavily-passage zonder `gaz`.

De Waalse bronpagina staat onder een industriegerichte URL; de gevonden
passage legt het verschil uit, maar deze proef valideert nog geen
huishoudspecifieke termijnen of uitzonderingen. Daarvoor is een afzonderlijke
controle van de volledige officiële pagina en van elke antwoordbewering nodig.
De algemene Eneco-vraag heeft evenmin een passage-gecontroleerd antwoord.
Er is niets gewijzigd aan de gehoste Karen, Framer, PDF-verwerking,
offertevergelijking of spraak.

Tijdens de diagnose verscheen een Tavily-sleutel in één tooluitvoer. De waarde
staat niet in deze bestanden. Roteer die sleutel in het Tavily-account voordat
de lokale proef verder wordt gebruikt.
