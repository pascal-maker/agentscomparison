# Karen × Vane — afzonderlijke lokale proef

Dit experiment vervangt nog niets in de gehoste Karen of Framer. Het test één
openbare antwoordroute: Vane/Perplexica zoekt en schrijft; de lokale proef
filtert bronnen en toont voorlopig alleen passende bronpassages. Er is geen
tweede Gemma-aanroep.

## Starten

Vereisten: Docker, Python 3.11+, Ollama met `llama3.2:latest` en
`nomic-embed-text:latest`. Deze modellen waren al lokaal aanwezig tijdens de
eerste installatie. Llama 3.2 is hier een aansluitproef, geen definitieve modelkeuze.

Voer uit vanuit de repositoryroot:

```sh
docker compose -p karen-vane-trial -f experiments/karen_vane/compose.yaml up -d
python -m pip install -r experiments/karen_vane/requirements.txt
python -m experiments.karen_vane.setup_local
python -m uvicorn experiments.karen_vane.app:app --host 127.0.0.1 --port 8011
```

Tijdens deze sessie wordt `/opt/anaconda3/bin/python` gebruikt; de afhankelijkheden
zijn daarin al aanwezig. Installeren is daar niet opnieuw nodig.

- Karen-testinterface: <http://127.0.0.1:8011>
- Vane zelf: <http://127.0.0.1:3008>
- Schema en API-documentatie: <http://127.0.0.1:8011/docs>

Vane kan vanuit Docker Ollama bereiken op `host.docker.internal:11434`.
De Vane-poort is alleen aan localhost gekoppeld. Gebruik uitsluitend openbare,
niet-persoonlijke vragen. Webzoeken benadert externe zoekmachines en websites;
alleen de gekozen taal- en embeddingmodellen draaien lokaal.

Stop de Python-server met Ctrl-C. Stop de container met:

```sh
docker compose -p karen-vane-trial -f experiments/karen_vane/compose.yaml stop
```

Dat bewaart het aparte Docker-volume. Deze proef gebruikt geen bestaande Vane-data.

## Bestanden

- `adapter.py`: modellen, providerselectie, Vane-aanroep en expliciete foutcodes.
- `app.py` en `index.html`: kleine lokale interface zonder PDF-upload of microfoon.
- `compose.yaml`: Vane met ingebouwde SearXNG op poort 3008.
- `searxng.yml`: alleen Google en Bing actief voor deze lokale proef. De
  standaardconfiguratie gaf op 2 oktober CAPTCHA-/toegangsfouten en geen
  resultaten. Dit omzeilt geen CAPTCHA; het gebruikt andere zoekmachines.
- `setup_local.py`: configureert uitsluitend de lokale Ollama-provider.
- `questions.json`: twintig publieke vragen met beoordelingscriteria.
- `benchmark.py`: voert vragen sequentieel uit en schrijft waarnemingen naar JSONL.
- `../../tests/test_karen_vane_trial.py`: geen netwerk of modelkosten.

## Wat Pydantic wel en niet doet

De adapter controleert onder andere de vorm van Vane's antwoord en de
bron-URL's. `sources_for_review` toont alleen overgebleven bronpassages.
`evidence_status` blijft **unverified**: formaat- en domeincontrole bewijzen
geen feitelijke juistheid. De fragmenten krijgen nieuwe doorlopende nummers
na filtering. Er worden nog geen prijsvelden uit proza geraden.

### Lokale proef met gestructureerde beweringen (9 oktober)

`structured_claims.py` laat lokaal `llama3.2:latest` JSON produceren voor één
bekend onderwerp: Eneco België en het verschil tussen voorschot en afrekening.
Het schema bevat een vaste entiteit, onderwerp, vier toegelaten beweringstypes,
de bron-URL en een letterlijk bewijsfragment. Pydantic weigert onbekende
velden, entiteiten en beweringstypes. Daarna verifieert code de exacte officiële
URL, het citaat en alle vooraf vastgelegde passages voor elke bewering. Alleen
goedgekeurde beweringen worden met vaste Nederlandse zinnen getoond.

```sh
python -m experiments.karen_vane.structured_claims
python -m experiments.karen_vane.structured_claims --live-page
PYTHONPATH=. pytest -q tests/test_karen_vane_structured_claims.py
```

Zonder optie gebruikt de proef een **lokale tekstfixture** uit de al
gecontroleerde Eneco-passages; met `--live-page` haalt ze de bekende officiële
pagina op, verifieert de uiteindelijke URL en geeft alleen de relevante
zichtbare sectie aan het lokale model. Beide varianten gebruiken geen Tavily-
of Browser Use-credit. In de fixture-run stelde het model vier beweringen voor;
drie doorstonden de passagecontrole. De live-pagina-run van 9 oktober leverde
vier voorstellen, waarvan slechts twee een bruikbaar letterlijk citaat hadden.
De bestaande deterministische Eneco-route controleert alle vier passagesets en
blijft daarom actief. De modelstap is nog geen route in de Karen- of
Vane-adapter en geen algemene bescherming tegen hallucinaties. Nieuwe
onderwerpen vereisen eigen entiteiten, toepasbaarheid en toetsbare bronnen.
Het generatieschema is eenvoudiger dan het Pydantic-validatiemodel: de volledige
Pydantic-JSON-schema-aanvraag liet deze lokale Ollama-modelrunner met HTTP 500
stoppen, terwijl een klein schema en een minimale schema-aanvraag werkten.

De proef toont bij ontbrekende bronnen een melding in plaats van ongefundeerd
modelproza. Dat is een conservatieve evaluatiekeuze; bronloze verduidelijkingen
moeten in een latere dialoogintegratie een eigen status krijgen. De UI kan
maximaal drie geaccepteerde gespreksparen in tabbladgeheugen bewaren; de huidige
bronpassages worden niet als modelantwoord in die geschiedenis opgenomen.
De API accepteert geen PDF- of vergelijkingssessievelden; dit is geen
inhoudelijke detectie van persoonsgegevens die iemand toch in vrije tekst typt.

### Eerste bronregels (4 oktober)

`source_relations.json` is de gedeelde kaart met officiële domeinen.
`karenEvidence.ts` gebruikt die kaart vóór Vane de antwoordtekst schrijft;
`source_policy.py` herhaalt de broncontrole op de Python-respons. Ze halen
uit een expliciete vraag het gewest, de leverancier, het energietype en het
onderwerp. Voor de proef staan alleen enkele bekende
overheidsdomeinen per gewest en de eigen Eneco-domeinen vast. Een URL van
`eneco.be.evil.test` telt niet als Eneco. Vragen met meerdere of ontkende
gewesten worden niet stilzwijgend aan één gewest toegewezen.

Vóór Vane schrijft vallen bronnen af die niet bij de expliciete vraag passen.
Daarna filtert de Python-adapter de aangeleverde bronpassages nogmaals. Zijn er geen passende bronnen, dan geeft hij
`insufficient_evidence`. Zijn er wel passende passages, dan toont hij
`sources_for_review` met links en bronfragmenten, **zonder het gegenereerde
modelantwoord**. De schrijver kan intern nog steeds een fout antwoord maken,
zelfs met passende bronnen; dit is een bescherming van de zichtbare proefuitvoer, geen bewijs dat zijn
uitspraken gecontroleerd zijn. Ook een toegelaten officieel domein bewijst
niet dat elk fragment relevant, actueel of waar is. De UI voegt zulke
bronfragmenten niet als een door Karen gegeven antwoord toe aan de gespreksgeschiedenis.

De huidige regels zijn een kleine pilot voor de drie waargenomen fouten.
Andere leveranciers en instanties moeten expliciet worden toegevoegd nadat
hun autoriteit is gecontroleerd. De testset bevat de verkeerd-gewestelijke
ketelpassage, het Singaporese Eneco-naamgenoot, leverancierfiltering en een
valse subdomeinnaam. Zie `SOURCE-POLICY-RESULTS-2026-10-04.md`.

### Eneco-facturen: eerste gecontroleerde antwoord (6 oktober)

Voor de expliciete vraag naar het verschil tussen een Eneco-voorschotfactuur en
jaarafrekening bewaart de zoekroute eigen Belgische Eneco-pagina's vóór de
embedding-deduplicatie. Het Vane-model maakt voor dit ene vraagtype geen
antwoordtekst meer: die schrijfstap liep in een live proef tegen de
90-secondenlimiet en had eerder feitelijke fouten gemaakt.

`invoice_answer.py` haalt Eneco's eigen afrekeningpagina rechtstreeks op.
Vier vaste antwoordzinnen hebben elk hun eigen vereiste passages uit die pagina.
Alleen als **alle** passages aanwezig zijn, geeft de adapter een kort antwoord
met `[1]` per zin en `evidence_status=passage_checked`. De status betekent dat
deze specifieke zinnen aan de huidige paginainhoud zijn getoetst; het is geen
algemene waarheidscontrole. Bij een ontbrekende pagina of passage toont Karen
alleen de eerder gevonden bronnen ter beoordeling.

De live route slaagde op 6 oktober: 19,32 seconden, één officiële bron in het
antwoord, drie Tavily-credits volgens de containerlog. Het antwoord kreeg ná
die live run alleen een presentatieverbetering: elke van de vier zinnen heeft nu
een afzonderlijke `[1]`; dit is met de lokale tests gecontroleerd en heeft geen
nieuwe Tavily-aanroep veroorzaakt. Zie `ENECO-INVOICE-RESULTS-2026-10-06.md`.
De bronselectieproef van 8 oktober herstelde deze route met één Tavily-aanroep;
zie `TAVILY-SOURCE-RESULTS-2026-10-08.md`.

### Waalse gasketel: gecontroleerd antwoord voor een woning (9 oktober)

Voor een expliciete vraag naar het **verschil** tussen onderhoud en periodieke
controle van een gasketel in Wallonië gebruikt de lokale adapter nu rechtstreeks
de [officiële residentiële Waalse pagina](https://energie.wallonie.be/home/performance-energetique-des-batiments/batiments-residentiels/renovation-walloreno/conseils-pratiques/se-chauffer-1/controle-periodique-et-diagnostic-approfondi-des-chaudieres.html).
`wallonia_boiler_answer.py` controleert de uiteindelijke URL en zichtbare Franse
passages voor drie vaste Nederlandse antwoordzinnen. De bronkaart toont een
letterlijk Frans fragment. Als één vereiste passage of de pagina ontbreekt,
blijft het antwoord `insufficient_evidence`; de adapter verzint geen regel en
start voor deze vraag ook geen betaalde Tavily-zoekactie. Industriële, meergewestelijke,
ontkende en expliciete frequentievragen blijven buiten deze smalle route.
Een live controle op 9 oktober gaf `answer_with_sources` en `passage_checked`.
Dit is een lokale Vane-proef, nog geen wijziging aan de gehoste Karen of Framer.

### Brusselse gasketel: frequentie met expliciete brandstof (9 oktober)

Voor de vraag hoe vaak een gasketel in Brussel gecontroleerd moet worden, haalt
de lokale adapter de [officiële burgerpagina van Leefmilieu Brussel](https://leefmilieu.brussels/verwarmingsketel)
rechtstreeks op. `brussels_boiler_answer.py` controleert de exacte bron-URL en
zichtbare passages over aardgas, de termijn van twee jaar en erkende technici.
Het antwoord noemt **aardgas** uitdrukkelijk; bij propaan, butaan of LPG wordt
deze route niet gebruikt. Ontbreekt de pagina of één van de passages, dan volgt
`insufficient_evidence` zonder termijn. De lokale live controle gaf
`answer_with_sources` en `passage_checked`; er is geen betaalde zoekaanroep
gedaan. Dit blijft een smalle, gecontroleerde route in de lokale proef en is nog
niet aan de Framer-microfoon gekoppeld.

## Evalueren

### Lokale zoekfix bouwen (3 oktober)

De aangepaste versie gebruikt de bestaande gepinde image voor afhankelijkheden,
maar bouwt Vane opnieuw uit commit `348feca3e378fb4157b217724ed508dc707f853f`.
Geef een lokale upstreamcheckout met die commit mee; eigen wijzigingen in die
checkout worden genegeerd. Alleen `upstream.patch` en `overrides/karenGuards.ts`
worden toegepast. De gerichte Node-tests draaien vóór de Next.js-build.

```sh
python experiments/karen_vane/build_patched.py /private/tmp/karen-vane-source
docker compose -p karen-vane-trial -f experiments/karen_vane/compose.yaml -f experiments/karen_vane/compose.patched.yaml up -d
python -m experiments.karen_vane.benchmark --cases experiments/karen_vane/regression_questions.json --output output/karen-vane/regression-2026-10-03.jsonl
```

De patch corrigeert het overslaan van expliciete NL/EN-zoekvragen en blokkeert
de rekenwidget bij vragen zonder numerieke berekening. De webzoekactie accepteert
normale zoektermen, lijsten en JSON-gecodeerde lijsten, en verwerpt ongeldige
invoer vóór een zoekaanroep. Dit zijn beperkte heuristieken, geen algemene
taalbegripsgarantie. De bestaande relevantiedrempels blijven ongewijzigd.

De override zet `KAREN_VANE_DIAGNOSTICS=1`: containerlogs bevatten openbare
vragen, zoektermen en aantallen vóór/na filtering. Zet dit op `0` om logging
uit te schakelen. Gebruik geen persoonlijke gegevens in deze proef.
Terug naar de oorspronkelijke image: voer dezelfde `up -d` uit met alleen
`compose.yaml`. De configuratie en het datavolume blijven behouden.

```sh
python -m experiments.karen_vane.benchmark --ids gas_price,eneco_bill,wallonia_boiler
python -m experiments.karen_vane.benchmark --output output/karen-vane/all.jsonl
PYTHONPATH=. pytest -q tests/test_karen_vane_trial.py
```

De runner stopt na de eerste dienstfout om geen identiek falende aanvragen te
blijven uitvoeren. `human_review: pending` is geen automatisch kwaliteitsoordeel.
Controleer de feitelijke passages, prijsperiode, eenheid en gewest. Geen van de
testvragen roept de Browser Use-offertevergelijker aan.

Instellingen via omgeving: `KAREN_VANE_URL`, `KAREN_VANE_PROVIDER`,
`KAREN_VANE_CHAT_MODEL`, `KAREN_VANE_EMBEDDING_MODEL`, `KAREN_VANE_TIMEOUT`.
De standaardtimeout is 90 seconden; er zijn geen automatische retries. Een
clienttimeout garandeert niet dat Vane zijn interne modelwerk heeft geannuleerd.
`KAREN_VANE_IMAGE` kan een vast Docker-digest bevatten voor herhaalbare proeven.

## Vóór productie

Deze proef is geen vervanging van de prijs- en bewijscontrole, regionale
bronvalidatie of dialoogroutering. De volgende stap na een geslaagde evaluatie
is één gedeelde antwoorddienst voor Framer-tekst en spraak. Persoonlijke PDF's
en de Browser Use-vergelijker blijven afzonderlijke routes. Verwijder Gemma pas
na die integratie en regressiecontrole.

De onderzochte upstreambron is `ItzCrazyKns/Vane` commit
`348feca3e378fb4157b217724ed508dc707f853f`. Dat is de broncode-inspectie; een
Docker-image heeft een eigen digest en hoeft niet dezelfde commit te bevatten.

De Compose-configuratie is vastgezet op image-digest
`sha256:0b61bf0d4470e9f2a9c71f794b72fab6e5a612177172770684c158a461f6896e`.
De officiële image is lokaal ongeveer 11,9 GB; de download bevatte onder meer
een laag van 2,6 GB. De eerder voorbereide native broncode-installatie is niet
nodig: de Docker-installatie is op 2 oktober succesvol gestart.

## Tavily aansluiten in de lokale proef (4 oktober)

Bouw de image zoals hierboven. Start vervolgens vanuit de repositoryroot:

```sh
python experiments/karen_vane/start_search_trial.py tavily
python -m experiments.karen_vane.benchmark --cases experiments/karen_vane/regression_questions.json --output output/karen-vane/tavily-full-2026-10-04.jsonl
```

De starter vereist `python-dotenv` (in de gebruikte Anaconda-omgeving aanwezig).
Hij leest uitsluitend `TAVILY_API_KEY` uit de omgeving of lokale `.env`-bestanden
voor de container. De sleutel wordt niet naar de buildcontext gekopieerd.
De optionele Compose-overlay `compose.tavily.yaml` kiest de provider.
Terugschakelen zonder rebuild: `python experiments/karen_vane/start_search_trial.py searxng`.

`overrides/karenWebSearch.ts` vertaalt Tavily-resultaten naar Vane's bestaande
zoekresultaatvorm. Alleen `web_search` krijgt deze adapter; andere zoektools
blijven hun bestaande implementatie gebruiken. Tavily gebruikt basic, vijf
resultaten, België als voorkeur, geen gegenereerd antwoord en geen automatische
parameterkeuze. Voor de herkende Waalse gasketelvraag gebruikt de proef één
Franse zoekterm en beperkt Tavily tot `energie.wallonie.be`. Andere expliciete
gewestvragen behouden de oorspronkelijke vraag als zoekterm. De Eneco-factuurvraag
zoekt breed bij Tavily omdat de domeinbeperking daar de twee benodigde
factuurpagina's verdreef; de bronselectie laat daarna uitsluitend passende
`eneco.be`-factuur-URL's door. Niet-herkende vragen kunnen nog meerdere
zoektermen en credits gebruiken. Er zijn geen retries of
stille providerfallbacks in de adapter. Ontbrekende sleutels, API-fouten en
ongeldige resultaatstructuren geven een generieke fout zonder responsebody.

Officiële bronnen met een herkende gewest- of leveranciersscope blijven vóór
de embedding-deduplicatie als afzonderlijke URL's behouden. Voor de Waalse
gasketelvergelijking vallen generieke gasnet- en schoorsteenpagina's af; de
officiële ketelpagina mag als kandidaat blijven als Tavily's korte fragment
het woord `gaz` weglaat. Dat is alleen bronselectie:
`sources_for_review` heeft `evidence_status=unverified` en bevat geen
gecontroleerd antwoord over Waalse regels. De resultaten en grenzen staan in
`TAVILY-SOURCE-RESULTS-2026-10-08.md`. Deze wijziging raakt geen
productie-, PDF-, microfoon- of offertevergelijkingsroute.
