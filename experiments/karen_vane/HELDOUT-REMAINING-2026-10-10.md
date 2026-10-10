# Resterende nieuwe vragen in de lokale Vane-proef (10 oktober 2026)

Deze meting betreft uitsluitend de lokale Vane/Tavily-proef. De gehoste Karen,
Framer, de PDF-route en Browser Use zijn niet gebruikt. De ruwe observaties
staan lokaal onder `output/karen-vane/`; dit bestand bevat de beoordeling.

## Wat veranderde

Drie expliciete vragen naar een officiële publieke uitleg starten nu een
webzoekactie, ook wanneer Vane's classifier die eerst overslaat. De
queryplanner gebruikt per vraag één gerichte query. De bronkaart en de
TypeScript- en Python-filters selecteren per onderwerp passende instanties en
pagina's. De vraag naar een persoonlijke contractprijs wordt vóór Vane of
Tavily afgehandeld: Karen vraagt naar de prijs per kWh en de periode in het
eigen contract of op de factuur.

## Live waarnemingen

| Vraag | Eerste zoekresultaat | Na onderwerpfilter en gerichte query |
| --- | --- | --- |
| Leverancier veranderen in Brussel | Leefmilieu-pagina over leverancierskeuze en een ongerelateerde BRUGEL-pagina over energiedelen. | Eén [BRUGEL-pagina met de stappen voor een leverancierswissel](https://brugel.brussels/themes/consommateurs-7/les-5-etapes-pour-changer-de-fournisseur-9). De eerste filterronde liet nul bronnen over, omdat Tavily's korte fragment het woord elektriciteit miste. Na controle van de volledige officiële pagina werd alleen voor dit exacte BRUGEL-pad een nauwe uitzondering toegevoegd. |
| Waalse aardgasmeterstand doorgeven | Een oud document over openbare aanbestedingen. | Eén [ORES-pagina over het doorgeven van meterstanden](https://www.ores.be/particulier/le-releve-index). De volledige pagina behandelt het onderwerp, maar het door Tavily gekozen fragment begint bij een minder relevante FAQ. ORES-instructies zijn alleen toepasbaar als ORES de betrokken netbeheerder is. |
| Eventuele opzegvergoeding bij Belgisch particulier elektriciteitscontract | Een Nederlandse ACM-pagina en een Vlaams parlementair voorstel. | Eén [CREG-pagina over contracttypes](https://www.creg.be/nl/consumenten/prijzen-en-tarieven/types-contracten-voor-elektriciteit-en-aardgas). De precieze regel en eventuele termijn zijn niet als gecontroleerde bewering aan de gebruiker gegeven; daarvoor moeten datum, contracttype en volledige bron worden geverifieerd. |
| Prijs uit eigen contract | Geen publieke bron kan de persoonlijke prijs aantonen. | `insufficient_evidence`, nul bronnen, gerichte vraag naar eigen contractgegevens. Een test met een HTTP-transport dat elke externe aanroep afkeurt bevestigt dat de route geen zoekdienst aanroept. |

Voor de eerste drie vragen rapporteert de evaluator uiteindelijk telkens één
bron van een vooraf aangewezen instantie en twee passende begrippengroepen.
Dat is een **bronselectiesignaal**, geen feitencontrole: alle drie blijven
`sources_for_review`, `evidence_status=unverified` en
`claim_verdict=not_evaluated`. Er wordt geen contractregel of bedrag uit de
fragmenten afgeleid. De persoonlijke vraag werd ook zonder draaiende
Vane-container beantwoord.

De volledige baseline gebruikte drie Tavily-credits, de eerste meting met
onderwerpfilter nog eens drie, een directe Brusselse diagnostische query één
en de laatste Brusselse herhaling één: **acht Tavily-credits** in deze
vervolgproef. Er waren geen Browser Use-kosten. De lokale proefcontainer is
na afloop gestopt.

## Grens voor verdere integratie

Deze zoekroute levert nu kandidaatbronnen voor de drie resterende publieke
vragen, maar geen gecontroleerde inhoudelijke antwoorden. Vooral het
irrelevante begin van het ORES-fragment en de juridische nuance rond
contractopzegging laten zien waarom een officieel domein en woordmatches niet
volstaan. Een volgende geïsoleerde stap is per gewenste antwoordzin de
volledige zichtbare passage, toepasselijkheid en datum te verifiëren, en bij
ontbrekend bewijs om verduidelijking te vragen of geen regel te formuleren.
Pas daarna is koppeling aan Karen/Framer zinvol.

Controle zonder betaalde zoekactie:

```sh
PYTHONPATH=. pytest -q tests/test_karen_vane_*.py
python experiments/karen_vane/build_patched.py /private/tmp/karen-vane-source
python -m experiments.karen_vane.evaluate_heldout --observations output/karen-vane/heldout-remaining-topic-policy-2026-10-10.jsonl
python -m experiments.karen_vane.evaluate_heldout --observations output/karen-vane/heldout-brussels-switch-2026-10-10.jsonl
```
