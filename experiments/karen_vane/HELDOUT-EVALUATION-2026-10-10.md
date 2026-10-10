# Karen × Vane: nieuwe publieke zoekvragen (10 oktober 2026)

Deze meting betreft alleen de lokale Vane/Tavily-proef. Er zijn geen PDF's,
Browser Use-offertevergelijkingen, Framer-wijzigingen of gehoste Karen-aanroepen
gedaan. `heldout_questions.json` bevat zes nieuwe vragen. Drie zijn vóór de
zoekguard-wijziging uitgevoerd; daarna zijn alleen de twee publieke zoekvragen
herhaald. De drie andere publieke vragen zijn nog niet live uitgevoerd.

## Vooraf: zoekroute sloeg vragen over

De Vlaamse maandpiekvraag, de federale sociaaltariefvraag en de vraag naar een
persoonlijke contractprijs gaven alle drie `insufficient_evidence` met nul
bronnen. De containerlog toont voor elk `raw.skipSearch=true`,
`guarded.skipSearch=true` en `final_sources=0`, zonder `provider_results`.
Voor deze drie beurten is dus geen Tavily-aanroep in de log geregistreerd.
De persoonlijke prijs hoort niet uit een publieke pagina te worden afgeleid;
de huidige melding vraagt echter nog niet gericht om contractgegevens.

`overrides/karenGuards.ts` herkent nu ook expliciete formuleringen als “waar
kan ik ... nakijken” en “op welke officiële ... pagina vind ik”, met behoud van
de opt-out en een nauwe uitzondering voor vragen naar de eigen contractprijs.
De opnieuw gebouwde geïsoleerde image doorstond 22 Node-tests, inclusief deze
nieuwe gevallen. De Python-proef doorstond 65 tests.

## Twee publieke vragen na de wijziging

| Vraag | Technisch resultaat | Bronbeoordeling |
| --- | --- | --- |
| Vlaamse maandpiek | `sources_for_review`, 5 bronnen, 42,62 s; één geregistreerde Tavily-credit | Alle vijf URL's liggen bij Vlaanderen.be, maar slechts één fragment bevat zowel “maandpiek” als “capaciteitstarief”. Dat fragment komt uit een pagina over **thuisbatterijen**. De vier andere fragmenten missen beide begrippen. De vraag naar de beste uitlegpagina is dus niet opgelost. |
| Geldigheidsperiode sociaal tarief aardgas | `sources_for_review`, 1 bron, 27,5 s; drie geregistreerde Tavily-credits voor drie zoekqueries | De overgebleven bron is Fluvius Prepaid. De vooraf vastgelegde bronverwachting was CREG of FOD Economie; geen van beide kwam in de zichtbare bronlijst. De fragmentwoorden komen wel overeen, maar bewijzen de huidige periode niet. |

De logs tonen voor de eerste vraag vijf Tavily-resultaten en vijf uiteindelijke
bronnen. Voor de tweede kwamen vijf resultaten terug per zoekquery; na de
bronselectie bleef één bron over. De logs bewaren niet alle kandidaat-URL's.
Daarom is niet vast te stellen of een CREG-pagina al bij Tavily ontbrak of later
door Vane is verwijderd. De evaluator rapporteert domein, begripsdekking en
antwoordstatus apart; `claim_verdict` blijft `not_evaluated`. De antwoorden
bevatten geen modelconclusie en hebben `evidence_status=unverified`.

De bestaande `source_relations.json` noemt voor Vlaanderen alleen
`vlaanderen.be` en `vreg.be`. Dat is te smal voor deze vraag: [Fluvius legt het
capaciteitstarief op de factuur uit](https://www.fluvius.be/nl/factuur-en-tarieven/capaciteitstarief/gezinnen-en-kleine-ondernemingen/op-mijn-factuur).
Voor het federale sociale tarief publiceert de [CREG een overzicht met
geldigheidsperiodes](https://www.creg.be/nl/consumenten/prijzen-en-tarieven/sociaal-tarief/sociaal-tarief-voor-energie).
Dat zijn handmatig gevonden referentiepagina's, geen bewijs dat Vane ze kon
vinden of hun inhoud correct zou weergeven.

## Besluit en volgende stap

De classifier-blokkade is in de lokale image verholpen. De algemene route is
nog niet geschikt om inhoudelijke antwoorden of prijzen aan Framer te geven:
een toegestaan officieel domein laat irrelevante pagina's door, terwijl de
federale vraag de gezaghebbende tariefbron mist. De huidige zichtbare
`sources_for_review`-status voorkomt wel dat Vane's ongecontroleerde proza als
antwoord verschijnt.

De kleinste volgende verbetering is een onderwerpgebonden broncontrole per
**afzonderlijke** pagina: laat voor maandpieken ook de netbeheerder toe, eis
daadwerkelijke tariefbegrippen in hetzelfde fragment, en stuur de federale
tariefvraag gericht naar CREG/FOD Economie. Vraag bij een persoonlijke prijs om
contractcontext in plaats van een publieke prijs te suggereren. Daarna kunnen
de resterende nieuwe vragen met een vooraf begrensd zoekbudget worden getest.
Pas als bronselectie en toepasselijkheid slagen, is een afzonderlijke proef
met bewering-voor-bewering verificatie zinvol.

Herhaal de reeds gemeten evaluatie zonder netwerk of credits:

```sh
python -m experiments.karen_vane.evaluate_heldout \
  --observations output/karen-vane/heldout-after-guard-2026-10-10.jsonl
PYTHONPATH=. pytest -q tests/test_karen_vane_*.py
```

De ruwe observaties staan lokaal onder `output/karen-vane/`; ze zijn niet
bedoeld als productiedata of als automatische waarheidslabels.
