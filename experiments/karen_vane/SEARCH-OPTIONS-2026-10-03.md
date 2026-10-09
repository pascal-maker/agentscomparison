# Zoek-API's voor de lokale Karen/Vane-proef

Documentatie gecontroleerd op 3 oktober 2026. Dit document vergelijkt leveranciersdocumentatie; het bewijst geen zoekkwaliteit voor Belgische energievragen. Er zijn voor dit document geen API-aanroepen uitgevoerd. Empirische proefresultaten worden afzonderlijk vastgelegd.

| Onderdeel | Brave Search API | Tavily Search API |
| --- | --- | --- |
| Gratis gebruik | $5 maandtegoed, gelijk aan 1.000 Search-requests; geen afzonderlijk gratis plan. | 1.000 credits per maand, zonder kredietkaart. |
| Betalen | Search: $5 per 1.000 requests. | Basic: 1 credit/request; advanced: 2. Pay-as-you-go: $0,008/credit; abonnementen: $0,0075–$0,005/credit. |
| Kaart | Vereist voor activatie, ook bij $0 vooruitbetaling. | Niet vereist voor gratis credits. |
| Authenticatie | `GET https://api.search.brave.com/res/v1/web/search`, header `X-Subscription-Token`. | `POST https://api.tavily.com/search`, header `Authorization: Bearer …`. |
| Zoekresultaten | `web.results`: titel, URL, `description`; `extra_snippets=true` geeft maximaal vijf extra fragmenten. | `results`: titel, URL, `content`, score; `include_answer=false` schakelt het gegenereerde antwoord uit. |
| Paginainhoud | De Web Search-resultaten bevatten snippets; volledige pagina-inhoud is hiermee niet gegarandeerd. | `include_raw_content` levert optioneel opgeschoonde pagina-inhoud als Markdown of tekst. |
| Land en taal | `country` voor land, `search_lang` voor inhoudstaal; `ui_lang` voor metadata. | `country="belgium"` verhoogt prioriteit bij `topic="general"`; `language="nl"` geeft taalvoorkeur, `filter_by_language=true` een strikt taalfilter. |
| Domeinen | `site:` in de query; Goggles voor filtering en rangschikking. | `include_domains`/`exclude_domains`; `include_domains_mode="restrict"` beperkt tot de opgegeven domeinen. |

Bronnen voor tarieven en inschrijving: [Brave prijzen](https://brave.com/search/api/), [Brave FAQ](https://api-dashboard.search.brave.com/documentation/resources/help-feedback), [Tavily credits en prijzen](https://docs.tavily.com/documentation/api-credits). Technische velden: [Brave Web Search](https://api-dashboard.search.brave.com/documentation/services/web-search), [Brave authenticatie](https://api-dashboard.search.brave.com/documentation/quickstart), [Tavily Search-reference](https://docs.tavily.com/documentation/api-reference/endpoint/search).

Bij Tavily levert `basic` volgens de documentatie bronfragmenten; `ultra-fast` levert NLP-samenvattingen. Kies voor deze proef expliciet `basic`, `auto_parameters=false`, `include_answer=false`, vijf resultaten en `include_usage=true`. Zo zijn instellingen en creditgebruik controleerbaar. [Tavily Search-reference](https://docs.tavily.com/documentation/api-reference/endpoint/search)

Brave documenteert $0 vooruitbetaling als manier om uitsluitend het maandtegoed te gebruiken. Controleer dat automatisch bijladen uitstaat. De FAQ verbiedt daarnaast opslag van ontvangen API-data zonder aanvullende afspraken; dat is relevant als ruwe zoekresultaten in benchmarkbestanden worden bewaard. [Brave FAQ](https://api-dashboard.search.brave.com/documentation/resources/help-feedback)

**Voorlopige keuze: Tavily basic als eerste lokale kandidaat.** De gratis inschrijving zonder kaart en expliciete domeinfilters maken een kleine proef eenvoudig. Dit is een praktische keuze, geen vastgestelde kwaliteitswinst boven SearXNG of Brave. Beoordeel dezelfde oorspronkelijke Nederlandstalige vragen op bereikbare officiële bronnen, bruikbare passages en responstijd. Een landvoorkeur bewijst niet dat een resultaat uit de juiste Belgische regio komt. Pas na die proef beslissen of vervanging gerechtvaardigd is; Brave blijft een tweede kandidaat.
