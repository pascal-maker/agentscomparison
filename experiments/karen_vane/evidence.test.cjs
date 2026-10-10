const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const source = ts.transpileModule(fs.readFileSync('src/lib/karenEvidence.ts','utf8'), {
  compilerOptions: {module:ts.ModuleKind.CommonJS,esModuleInterop:true,target:ts.ScriptTarget.ES2022},
}).outputText;
const mod={exports:{}};
vm.runInNewContext(source,{module:mod,exports:mod.exports,URL,require:name=>{
  if(name==='./karenSourceRelations.json') return require('./src/lib/karenSourceRelations.json');
  throw Error('unexpected dependency '+name);
}});
const select=mod.exports.selectEvidence;
const chunk=(url,content)=>({content,metadata:{url,title:'Source'}});

test('before-writer selection rejects Brussels rule for Wallonia',()=>{
  const got=select('Gasketelcontrole in Wallonië?',[
    chunk('https://leefmilieu.brussels/ketel','Gasketel in Brussel'),
    chunk('https://energie.wallonie.be/ketel','Chaudière gaz Wallonie'),
  ]);
  assert.equal(got.length,1);assert.equal(got[0].metadata.url,'https://energie.wallonie.be/ketel');
});
test('Walloon gas boiler comparison rejects housing and fuel-tank pages',()=>{
  const question='Onderhoud en periodieke controle gasketel in Wallonië';
  const got=select(question,[
    chunk('https://logement.wallonie.be/storage/reparations.pdf','Entretien et contrôle des brûleurs gaz chaudière Wallonie'),
    chunk('https://www.wallonie.be/fr/demarches/gerer-sa-citerne-mazout','Entretien et contrôle de la citerne mazout chaudière gaz Wallonie'),
    chunk('https://energie.wallonie.be/home/controle-chaudiere.html','Entretien et contrôle périodique des chaudières gaz en Wallonie'),
  ]);
  assert.deepEqual(Array.from(got, x=>x.metadata.url), ['https://energie.wallonie.be/home/controle-chaudiere.html']);
});
test('Walloon boiler comparison needs passages for both requested concepts',()=>{
  const got=select('Onderhoud en periodieke controle gasketel in Wallonië',[
    chunk('https://energie.wallonie.be/home/gasnet','Gaz et chaudière en Wallonie'),
    chunk('https://energie.wallonie.be/home/controle','Contrôle périodique chaudière gaz Wallonie'),
    chunk('https://energie.wallonie.be/home/chaudiere-beide','Entretien et contrôle périodique chaudière gaz Wallonie'),
  ]);
  assert.deepEqual(Array.from(got,x=>x.metadata.url),['https://energie.wallonie.be/home/chaudiere-beide']);
});
test('short Tavily excerpt does not discard primary boiler page or admit chimney page',()=>{
  const question='Onderhoud en periodieke controle van een gasketel in Wallonië';
  const got=select(question,[
    {metadata:{url:'https://energie.wallonie.be/home/vous-avez-dit-entretien-des-chaudieres.html',
      title:'Vous avez dit entretien des chaudières et des brûleurs?'},
      content:"L'entretien des chaudières n'est pas réglementairement obligatoire. Le contrôle périodique l'est."},
    {metadata:{url:'https://energie.wallonie.be/home/les-cheminees.html',title:'Les cheminées : un élément déterminant'},
      content:"Pour les appareils au gaz, l'entretien de la chaudière est utile. Le contrôle périodique est prévu."},
  ]);
  assert.deepEqual(Array.from(got,x=>x.metadata.url),
    ['https://energie.wallonie.be/home/vous-avez-dit-entretien-des-chaudieres.html']);
});
test('before-writer selection rejects Singapore name collision and spoofed host',()=>{
  const got=select('What is Eneco?',[
    chunk('https://enecoenergy.com/','Eneco Energy Limited Singapore'),
    chunk('https://eneco.be.evil.test/','Eneco supplier'),
    chunk('https://eneco.be/nl/','Eneco levert energie'),
  ]);
  assert.equal(got.length,1);assert.equal(got[0].metadata.url,'https://eneco.be/nl/');
});
test('ambiguous regions and mismatched topic cannot pass',()=>{
  assert.equal(select('Wallonië en Brussel gasketel',[
    chunk('https://energie.wallonie.be/ketel','Gas ketel Wallonie')]).length,0);
  assert.equal(select('Eneco voorschotfactuur',[
    chunk('https://eneco.be/nl/over','Over Eneco')]).length,0);
});
test('invoice pages survive before embedding dedup, with official Belgian pages first',()=>{
  const candidates=[
    chunk('https://callmepower.be/nl/eneco/factuur','Eneco voorschotfactuur en afrekening'),
    chunk('https://eneco.be/nl/contact/my-eneco','Eneco afrekening'),
    chunk('https://eneco.be/nl/contact/alles-over-je-energietarief','Eneco voorschotfactuur en afrekening'),
    chunk('https://eneco.be/nl/contact/alle-info-over-je-voorschotfactuur','Eneco voorschotfactuur'),
    chunk('https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie','Eneco voorschotten en afrekening'),
    chunk('https://eneco.be/nl/contact/alles-over-je-afrekening-van-energie','Duplicate'),
  ];
  const got=mod.exports.selectInvoiceEvidence('Zoek bij Eneco verschil voorschotfactuur jaarafrekening',candidates);
  assert.equal(got.length,2);
  assert.match(got[0].metadata.url,/alles-over-je-afrekening-van-energie/);
  assert.match(got[1].metadata.url,/alle-info-over-je-voorschotfactuur/);
  assert.ok(got.every(item=>item.metadata.url.startsWith('https://eneco.be/')));
});

test('Flemish capacity peak keeps topic pages and rejects incidental official pages',()=>{
  const question='Waar kan ik voor Vlaanderen nakijken hoe mijn maandpiek voor het capaciteitstarief bepaald wordt?';
  const findings=[
    {metadata:{url:'https://www.vlaanderen.be/zonnepanelen/thuisbatterij',title:'Thuisbatterij'},
      content:'De maandpiek bepaalt het capaciteitstarief.'},
    {metadata:{url:'https://www.fluvius.be/nl/factuur-en-tarieven/capaciteitstarief',title:'Het capaciteitstarief op mijn factuur'},
      content:'De maandpiek is de hoogste kwartierpiek; het capaciteitstarief gebruikt maandpieken.'},
    {metadata:{url:'https://www.fluvius.be.evil.test/capaciteitstarief',title:'Capaciteitstarief'},
      content:'Maandpiek en capaciteitstarief.'},
  ];
  assert.deepEqual(Array.from(select(question,findings),x=>x.metadata.url),
    ['https://www.fluvius.be/nl/factuur-en-tarieven/capaciteitstarief']);
  assert.deepEqual(Array.from(mod.exports.authorityDomains(question)),
    ['fluvius.be','vreg.be','vlaanderen.be']);
});

test('social tariff period requires tariff authority and rejects premium pages',()=>{
  const question='Op welke officiële Belgische pagina vind ik de geldigheidsperiode van het huidige sociaal tarief voor aardgas?';
  const findings=[
    {metadata:{url:'https://prepaid.fluvius.be/sociaal-tarief',title:'Het sociaal tarief'},
      content:'Sociaal tarief voor aardgas per kwartaal.'},
    {metadata:{url:'https://www.creg.be/nl/sociaaltariefpremie',title:'Sociaaltariefpremie'},
      content:'Sociaal tarief voor aardgas Q4 2026.'},
    {metadata:{url:'https://www.creg.be/nl/sociaal-tarief-voor-energie',title:'Sociaal tarief voor energie'},
      content:'Het sociaal tarief voor aardgas geldt in Q4 2026.'},
  ];
  assert.deepEqual(Array.from(select(question,findings),x=>x.metadata.url),
    ['https://www.creg.be/nl/sociaal-tarief-voor-energie']);
  assert.deepEqual(Array.from(mod.exports.authorityDomains(question)),
    ['creg.be','economie.fgov.be']);
});
