# Rechtstreekse Tavily-proef

Dezelfde drie oorspronkelijke vragen zijn eenmaal rechtstreeks naar Tavily
gestuurd, zonder Vane, Llama, modelherformulering of lokaal embeddingfilter.
Instellingen: basic, vijf resultaten, country=belgium, auto_parameters=false,
include_answer=false, include_raw_content=false. Geen domein- of strikt
taalfilter toegepast. Alle requests gaven HTTP 200 en rapporteerden één credit:
**drie credits totaal**. Het accountsaldo en eventuele facturatie zijn niet
gecontroleerd; dit is geen bevestiging dat de requests binnen gratis tegoed vielen.

| Oorspronkelijke vraag | Tijd | Waarneming | Beoordeling van zoekresultaten |
| --- | ---: | --- | --- |
| Eneco voorschotfactuur versus jaarafrekening | 1,72 s | 5 resultaten; Vlaanderen en twee officiële Eneco-pagina's over precies deze facturen | Bruikbaar bronmateriaal gevonden |
| Wallonië: onderhoud versus periodieke ketelcontrole | 2,02 s | 5 resultaten; sectorinformatie over Wallonië, maar ook Brussel en Vlaanderen | Onvoldoende: geen Waalse overheidsbron in top 5; gewesten worden gemengd |
| What is Eneco? Search the web and cite your sources. | 1,17 s | 5 resultaten; Eneco About Us en Eneco België-perspagina; ook een oud document uit 2018 | Bruikbaar voor algemene omschrijving; actualiteit moet per claim gecontroleerd worden |

Relevante gevonden leverancierspagina's:
- https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie
- https://eneco.be/nl/contact/alle-info-over-je-voorschotfactuur
- https://www.eneco.nl/en/about-us

Beoordeling gebaseerd op teruggegeven URL's en passages, niet op een afzonderlijke
volledige pagina-audit of op een gegenereerd antwoord. Twee van de drie gevallen
hebben bruikbaar officieel bronmateriaal; de Wallonië-vraag is nog niet geslaagd.
De Eneco-factuurpassages gaan daadwerkelijk over voorschotten en verrekening.
De andere Eneco-vraag vindt bedrijfsinformatie in plaats van Discord-pagina's.

Dit is een betere waarneming dan de eerdere Vane/SearXNG-run, maar geen zuivere
vergelijking van alleen zoekproviders: die eerdere run gebruikte modelgegenereerde
zoektermen en filtering. De tijden hierboven meten uitsluitend Tavily, terwijl
de eerdere 31–38 seconden de hele Vane-antwoordketen maten. Ze mogen niet als
gelijke end-to-end-snelheidsmetingen worden vergeleken.

## Advies

Kies Tavily als eerste kandidaat voor een optionele zoekadapter in de lokale
Vane-proef. Valideer daarna dezelfde vragen door de volledige keten. Geef de
Wallonië-vraag een Franse zoekvariant en controleer passende officiële Waalse
bronnen; neem Vlaamse of Brusselse regels niet over voor Wallonië. Dit vervolg
is nog niet geïmplementeerd. Ook de ongefundeerde antwoorden van Llama zijn met
deze zoekproef niet opgelost.

Brave is alleen op documentatie vergeleken; er was geen sleutel beschikbaar.
Zie [zoekdienstenonderzoek](SEARCH-OPTIONS-2026-10-03.md). Geen nieuwe accounts,
providerwissel, modelwissel of productie-/Framerwijziging uitgevoerd.

## Reproduceren

`probe_tavily.py` gebruikt de bestaande TAVILY_API_KEY uit de omgeving of lokale
.env-bestanden, met httpx en python-dotenv. Sleutelwaarden worden niet gelogd.
De probe doet geen retries en stopt bij API-fouten. Het resultaatbestand wordt
exclusief aangemaakt, zodat opnieuw uitvoeren niet stilzwijgend extra requests
veroorzaakt of eerder bewijs overschrijft.

```sh
/opt/anaconda3/bin/python -m experiments.karen_vane.probe_tavily
```

Ruwe lokale waarnemingen: `output/karen-vane/tavily-direct-2026-10-03.jsonl`
(gitignored). De probe is bewust beperkt tot deze drie openbare regressievragen.
De API-instellingen en creditbetekenis zijn gecontroleerd in de
[Tavily Search-documentatie](https://docs.tavily.com/documentation/api-reference/endpoint/search)
en [creditdocumentatie](https://docs.tavily.com/documentation/api-credits).
