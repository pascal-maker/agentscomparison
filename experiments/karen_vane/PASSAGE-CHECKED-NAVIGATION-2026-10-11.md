# Gecontroleerde vindplaatsen in de lokale Vane-proef (11 oktober 2026)

De drie publieke vervolgvragen vroegen **waar** officiële uitleg staat. De
lokale Karen-adapter beantwoordt precies die vindplaatsvraag nu rechtstreeks,
zonder Vane een vrij antwoord te laten schrijven. Dit verandert de gehoste
Karen, Framer, PDF-route en offertevergelijker niet. Jev is niet toegevoegd.

Voor elk van de drie onderwerpen haalt `public_navigation_answer.py` de exact
vastgelegde HTTPS-pagina op. De code controleert na eventuele redirects opnieuw
host en pad en eist meerdere zichtbare passages uit de volledige pagina.
Alleen dan toont hij een vaste Nederlandse zin met de officiële bron. Bij een
fout, redirect naar een andere pagina of ontbrekende passage geeft hij
`insufficient_evidence` en start hij geen zoekactie als alternatief.

| Vraag | Rechtstreeks gecontroleerde pagina | Grens van het antwoord |
| --- | --- | --- |
| Leverancier veranderen in Brussel | [BRUGEL: vijf stappen](https://brugel.brussels/themes/consommateurs-7/les-5-etapes-pour-changer-de-fournisseur-9) | Wijst naar de uitleg; vergelijkt zelf geen aanbiedingen. |
| Waalse aardgasmeterstand doorgeven | [ORES: meterstand doorgeven](https://www.ores.be/particulier/le-releve-index) | Geldt als ORES de netbeheerder is; bij een andere beheerder vraagt Karen welke. |
| Eventuele vergoeding bij opzegging van een particulier elektriciteitscontract | [CREG: contracttypes](https://www.creg.be/nl/consumenten/prijzen-en-tarieven/types-contracten-voor-elektriciteit-en-aardgas) | Wijst naar de passage over opzegging en vergoeding; geeft geen termijn of oordeel over een persoonlijk contract. |

De actuele CREG-webpagina noemt een opzegtermijn van één maand, terwijl een
[CREG-infografiek uit november 2025](https://www.creg.be/sites/default/files/assets/Prices/InfographResNl.pdf)
drie weken noemt. Deze proef beslist niet welke publicatie juridisch leidend
is. Daarom komt geen termijn in de vaste antwoordzin. Een juridische
interpretatie vereist een afzonderlijke controle van de huidige regel en
toepasselijkheid.

De live lokale meting op 11 oktober leverde voor alle drie
`answer_with_sources`, één bron en `evidence_status=passage_checked` op. De
evaluator houdt `claim_verdict=manual_review_required`: passagecontrole bewijst
niet dat ieder mogelijk detail actueel of op de persoonlijke situatie van
toepassing is. De ruwe lokale observatie staat in
`output/karen-vane/heldout-navigation-passage-2026-10-11.jsonl`. Deze run deed
drie directe, leesbare HTTP-verzoeken aan de officiële sites en gebruikte
**nul Tavily- en nul Browser Use-credits**. De proefcontainer hoefde niet te
draaien.

De drie bestaande bronfiltertests zijn apart gebleven van de nieuwe
antwoordroute. De gerichte Python-suite telt 79 geslaagde tests, waaronder
afwijzing bij ontbrekende passages en bij een redirect naar een andere host.

```sh
PYTHONPATH=. pytest -q tests/test_karen_vane_*.py
python -m experiments.karen_vane.evaluate_heldout \
  --observations output/karen-vane/heldout-navigation-passage-2026-10-11.jsonl
```
