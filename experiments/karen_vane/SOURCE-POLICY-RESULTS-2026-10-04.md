# Bronrelaties in de lokale Vane-proef — 4 oktober 2026

## Wat is toegevoegd

De Vane-zoekroute en Python-adapter delen een kleine, expliciete bronkaart
(`source_relations.json`). Ze lezen uit een
publieke vraag het genoemde gewest (Wallonië, Brussel of Vlaanderen), Eneco als
leverancier, gas of elektriciteit en het onderwerp factuur of ketel. De kaart
bevat alleen enkele bekende officiële gewestdomeinen en de eigen domeinen
`eneco.be` en `eneco.nl`. Exacte hostgrenzen voorkomen dat een domein als
`eneco.be.evil.test` als officieel telt. Een bron over een ander expliciet
genoemd gewest, energietype of onderwerp valt ook af.

De eerste bronselectie gebeurt **vóór** Vane's schrijfstap, nadat de onderzoeker
zijn bronnen heeft geselecteerd. De adapter herhaalt de controle op de zichtbare
respons. Hij laat het conceptantwoord nu nooit als bevestigd
antwoord zien: bij passende passages toont hij alleen links en fragmenten met
status `sources_for_review`; bij geen passende passages meldt hij
`insufficient_evidence`. Dat is bewust streng. Een passend domein is geen
bewijs dat elke zin in een automatisch antwoord klopt. Meerregio- en ontkende
regiovragen worden niet aan een enkele regio toegewezen.

## Controle met de opgeslagen volledige Tavily-proef

Deze controle hergebruikt de ruwe uitkomsten van 4 oktober, zonder nieuwe
Tavily-credits of Ollama-aanroepen:

| Vraag | Vane-bronnen | Na bronkaart | Zichtbare uitkomst |
| --- | ---: | ---: | --- |
| Eneco voorschotfactuur versus jaarafrekening | 2 | 1 | Alleen een fragment van `eneco.be`; het foutieve modelantwoord verdwijnt. Het fragment alleen bevestigt het volledige verschil nog niet. |
| Waalse gasketelregels | 1 | 0 | De Fireforum-passage over Brusselse regels valt af; geen inhoudelijke conclusie. |
| Wat is Eneco? | 5 | 0 | Ook het Singaporese naamgenootbedrijf valt af. De resterende niet-officiële pagina's bieden in deze strenge proef onvoldoende autoriteit. |

Dit is een **replay van eerder opgehaalde bronnen**, geen nieuw end-to-end
kwaliteitsoordeel. De bronkaart kan een passende officiële pagina niet
terughalen als Vane die eerder bij deduplicatie verloor. De modelschrijver kan
intern nog steeds fouten maken; de adapter onderdrukt ze in de proef-UI.
Voor andere leveranciers en autoriteiten bevat de kaart nog geen expliciete
relaties. Ook officiële pagina's kunnen verouderd of irrelevant zijn.

## Verificatie en vervolg

`PYTHONPATH=. /opt/anaconda3/bin/pytest -q tests/test_karen_vane_trial.py
tests/test_karen_vane_source_policy.py` → **17 geslaagd**. Tests dekken de
Brussel/Wallonië-verwisseling, Eneco/Singapore-verwisseling, leverancierfilter,
hostgrenzen, onderwerp/energietype en dubbelzinnige regio's. De aangepaste
lokale Vane-image is opnieuw gebouwd met bronselectie vóór de schrijfstap.
De build voerde **13 Node-regressietests** uit; Next.js-compilatie en
TypeScript-controle slaagden. De image is geactiveerd in de lokale Docker-proef.
De Python-adapter en lokale webinterface zijn ook bijgewerkt. Er zijn voor deze
wijziging geen nieuwe Tavily-credits gebruikt; de drie vragen zijn niet opnieuw
live door de hele keten uitgevoerd.

Voor een volwaardig antwoord moet bronselectie ook vóór Vane's deduplicatie
plaatsvinden, zodat geschikte passages niet eerst verloren gaan. Daarna
moet elke concrete bewering aan een specifieke passage worden getoetst. Tot dat
werkt, presenteert de proef bronmateriaal ter beoordeling in plaats van een
ongecontroleerde conclusie. Er is niets naar Framer of productie gepubliceerd.
