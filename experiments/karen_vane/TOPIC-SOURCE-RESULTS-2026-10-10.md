# Onderwerpgerichte bronnen in de lokale Vane-proef (10 oktober 2026)

Deze vervolgproef verandert alleen `experiments/karen_vane`. De gehoste Karen,
Framer, PDF-route en Browser Use-offertevergelijker zijn niet aangeroepen of
gewijzigd. De ruwe lokale observaties staan onder `output/karen-vane/`.

## Aanpassing

De gedeelde bronkaart bevat nu twee smalle onderwerprelaties:

- Vlaamse maandpiek/capaciteitstarief: Fluvius, VREG of Vlaanderen.be, met
  maandpiek en capaciteitstarief in **hetzelfde** fragment en een passend
  paginaonderwerp in titel of pad.
- Geldigheidsperiode van het Belgische sociale aardgastarief: CREG of FOD
  Economie, met sociaal tarief, gas en een periodeaanduiding in hetzelfde
  fragment. Pagina's over de afzonderlijke sociaaltariefpremie vallen af.

De TypeScript-selectie vóór Vane's schrijver en de Python-selectie op het
antwoord gebruiken dezelfde bronkaart en onderwerpvoorwaarden. De
queryplanner doet voor deze twee vraagtypen één gerichte zoekactie. Voor het
sociaal tarief voegt hij het huidige UTC-jaar toe; dat is een zoekterm en
geen bewijs dat een gevonden tarief actueel is. De zichtbare status blijft
`sources_for_review` met `evidence_status=unverified`.

## Waarnemingen

| Vraag | Vóór deze aanpassing | Na deze aanpassing |
| --- | --- | --- |
| Vlaamse maandpiek | Vijf Vlaanderen.be-bronnen, waaronder vier fragmenten zonder de gevraagde begrippen. | Drie Fluvius-pagina's, alle drie met beide begrippen. De [gerichte uitleg op de factuurpagina](https://www.fluvius.be/nl/factuur-en-tarieven/capaciteitstarief/gezinnen-en-kleine-ondernemingen/op-mijn-factuur) staat ertussen. Eén andere bron is een oudere Fluvius-blog; een lexicale match bewijst niet dat alle details nog actueel zijn. |
| Periode sociaal aardgastarief | Alleen Fluvius Prepaid, niet de vooraf vastgelegde federale tariefautoriteit. | Eén [CREG-overzichtspagina](https://www.creg.be/nl/consumenten/prijzen-en-tarieven/sociaal-tarief/sociaal-tarief-voor-energie) met aardgas en kwartaalregels in het zoekfragment; geen prijs of inhoudelijke conclusie in Karen's antwoord. |

De eerste federale query na de bronfilterwijziging gaf nul bronnen: Tavily
leverde vooral oude CREG-jaarverslagen en één FOD-pagina waarvan het korte
fragment geen tariefperiode bevatte. Een directe diagnostische query met
“sociaal tarief voor energie”, aardgas en 2026 vond de CREG-overzichtspagina.
Na deze querywijziging gaf de volledige Vane-route ook die ene CREG-bron.
We weten daarmee waarom de eerste query faalde; we hebben geen algemeen
bewijs dat zulke queries in latere kwartalen altijd de juiste pagina geven.

De volledige routes gebruikten drie Tavily-credits (twee bij de eerste
herhaling, één bij de finale federale herhaling). De twee directe
diagnostische zoekacties gebruikten elk één credit: **vijf credits in deze
vervolgproef**. Er waren geen Browser Use-kosten. De finale federale route
duurde 25,5 seconden; de Vlaamse route 40,48 seconden.

De openbare CREG- en FOD-pagina's blokkeerden directe automatische uitlezing
in deze sessie (403 respectievelijk een menselijke verificatiepagina).
Daarom geldt het Tavily-fragment alleen als kandidaatbron. De actuele
geldigheidsperiode en eventuele bedragen zijn niet onafhankelijk vanuit de
volledige pagina bevestigd. De evaluator rapporteert voor beide finale
vragen een passende bron en begrippen, maar `claim_verdict=not_evaluated`.

## Resterende grens

De twee geteste vraagtypen kunnen nu een plausibele officiële bron tonen.
Algemene Karen-antwoorden mogen daar nog niet uit volgen. De overige drie
publieke vragen in `heldout_questions.json` zijn nog niet live getest, en de
persoonlijke contractprijsvraag vraagt nog geen gerichte verduidelijking.
Een volgende stap is deze resterende vragen met een vooraf begrensd
zoekbudget te testen en per concrete bewering de volledige zichtbare bron
te controleren. De lokale proef mag pas aan Framer worden gekoppeld als die
grens voor de gewenste vraagtypen aantoonbaar werkt.

Tests zonder betaalde zoekactie:

```sh
PYTHONPATH=. pytest -q tests/test_karen_vane_*.py
python experiments/karen_vane/build_patched.py /private/tmp/karen-vane-source
```

De Docker-build voert de gerichte Node-tests en de TypeScript-compile uit;
voor de build is een checkout van de gepinde Vane-revisie nodig.
