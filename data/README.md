# Karen expert-ingestie

Deze mappen scheiden de fasen van de beheerde ingestiepipeline:

- `experts/`: gevalideerd expertregister (`experts.jsonl`)
- `sources/`: expliciet goedgekeurde bronmetadata (`sources.jsonl`)
- `raw/`: later opgehaalde, ongewijzigde broninhoud
- `normalized/`: later genormaliseerde documenten
- `chunks/`: later semantisch gechunkte documenten

In deze eerste iteratie blijven `raw/`, `normalized/` en `chunks/` leeg. De
scripts voor die fasen stoppen bewust totdat de expert- en bronselectie
menselijk is goedgekeurd.
