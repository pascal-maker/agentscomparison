const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const evidenceSource = ts.transpileModule(fs.readFileSync('src/lib/karenEvidence.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2022 },
}).outputText;
const evidence = { exports: {} };
vm.runInNewContext(evidenceSource, { module: evidence, exports: evidence.exports, URL,
  require: name => name === './karenSourceRelations.json'
    ? require('./src/lib/karenSourceRelations.json') : (() => { throw Error('unexpected '+name); })(),
});
function load(env, fetch, searx = () => { throw Error('unexpected fallback'); }) {
  const mod = { exports: {} };
  const source = ts.transpileModule(fs.readFileSync('src/lib/karenWebSearch.ts', 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, esModuleInterop: true, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  vm.runInNewContext(source, { module: mod, exports: mod.exports, process: {env}, fetch,
    AbortSignal, require: name => name === 'zod' ? require('zod') : name === './searxng'
      ? { searchSearxng: searx } : name === './karenEvidence'
      ? evidence.exports : { trace: () => {} } });
  return mod.exports;
}
test('default keeps SearXNG query and options', async () => {
  let args;
  const search = load({}, () => {throw Error('unexpected Tavily');}, (...a) => { args=a; return {results:[],suggestions:[]}; }).searchWeb;
  await search('Eneco', {language:'nl'});
  assert.deepEqual(args, ['Eneco', {language:'nl'}]);
});
test('Tavily maps evidence without generated answer; fixed basic settings', async () => {
  const search = load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'}, async (url, options) => {
    assert.equal(url,'https://api.tavily.com/search');
    assert.equal(options.headers.Authorization,'Bearer test-secret');
    const body = JSON.parse(options.body);
    assert.equal(body.query,'Eneco'); assert.equal(body.include_answer,false);
    assert.equal(body.search_depth,'basic'); assert.equal(body.auto_parameters,false);
    assert.equal(body.max_results,5); assert.equal(body.country,'belgium');
    assert.ok(options.signal);
    return {ok:true,json:async()=>({results:[{title:'Eneco',url:'https://eneco.be/',content:'Evidence'}],answer:'Ignore'})};
  }).searchWeb;
  const result = await search('Eneco');
  assert.equal(result.results[0].content,'Evidence'); assert.equal(result.suggestions.length,0);
  assert.equal(result.answer,undefined);
});
test('missing key, HTTP, malformed results and network failures do not fallback or leak', async () => {
  await assert.rejects(load({KAREN_WEB_SEARCH_PROVIDER:'tavily'},()=>{throw Error('unexpected');}).searchWeb('x'),/key missing/);
  for (const fetch of [async()=>({ok:false}),async()=>({ok:true,json:async()=>({results:[{url:'javascript:bad'}]})}),async()=>{throw Error('test-secret');}]) {
    await assert.rejects(load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'},fetch).searchWeb('x'),/^Error: Tavily search unavailable$/);
  }
});

test('explicit Wallonia scope restricts Tavily to the official authority', async () => {
  const search = load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'}, async (_, options) => {
    const body = JSON.parse(options.body);
    assert.deepEqual(Array.from(body.include_domains), ['energie.wallonie.be']);
    assert.equal(body.include_domains_mode, 'restrict');
    return {ok:true,json:async()=>({results:[{title:'Chaudière gaz',url:'https://energie.wallonie.be/controle',content:'Contrôle chaudière gaz Wallonie'}]})};
  }).searchWebForQuestion('Gasketel in Wallonië');
  const result = await search('Wallonie entretien contrôle périodique chaudière gaz');
  assert.equal(result.results.length, 1);
});

test('Eneco invoice query stays broad at Tavily while downstream policy checks URLs', async () => {
  const question = 'Zoek bij Eneco het verschil tussen een voorschotfactuur en een jaarafrekening.';
  const search = load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'}, async (_, options) => {
    const body = JSON.parse(options.body);
    assert.equal(body.query, question);
    assert.equal(body.include_domains, undefined);
    return {ok:true,json:async()=>({results:[]})};
  }).searchWebForQuestion(question);
  await search(question);
});

test('social tariff period limits Tavily to federal tariff authorities', async () => {
  const question='Op welke officiële Belgische pagina vind ik de geldigheidsperiode van het huidige sociaal tarief voor aardgas?';
  const search=load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'}, async (_,options)=>{
    const body=JSON.parse(options.body);
    assert.deepEqual(Array.from(body.include_domains),['creg.be','economie.fgov.be']);
    return {ok:true,json:async()=>({results:[]})};
  }).searchWebForQuestion(question);
  await search(`CREG sociaal tarief voor energie aardgas ${new Date().getUTCFullYear()} kwartaal`);
});

test('Belgian contract exit limits Tavily to Belgian federal consumer authorities', async () => {
  const question='Waar staat de officiële uitleg over een eventuele opzegvergoeding bij een particulier elektriciteitscontract in België?';
  const search=load({KAREN_WEB_SEARCH_PROVIDER:'tavily',TAVILY_API_KEY:'test-secret'}, async (_,options)=>{
    const body=JSON.parse(options.body);
    assert.deepEqual(Array.from(body.include_domains),['creg.be','economie.fgov.be']);
    return {ok:true,json:async()=>({results:[]})};
  }).searchWebForQuestion(question);
  await search('CREG opzegvergoeding energiecontract particulier elektriciteit België');
});
