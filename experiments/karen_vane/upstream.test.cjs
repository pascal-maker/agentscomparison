const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const root = path.join(process.cwd(), 'src/lib/agents/search');

function load(file, mocks = {}) {
  const output = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
  }).outputText;
  const mod = { exports: {} };
  vm.runInNewContext(output, { module: mod, exports: mod.exports, console, process, URL,
    crypto: require('node:crypto').webcrypto,
    require: name => {
      if (name === './karenSourceRelations.json') return require('./src/lib/karenSourceRelations.json');
      if (name === '@/lib/karenEvidence') return evidence;
      if (name === '@/lib/karenWebSearch') return { searchWeb: async () => ({ results: [], suggestions: [] }),
        searchWebForQuestion: () => async () => ({ results: [], suggestions: [] }) };
      if (name in mocks) return mocks[name];
      if (name.endsWith('karenGuards')) return guards;
      if (name === 'zod') return require('zod');
      throw new Error('Unexpected dependency: ' + name);
    },
  });
  return mod.exports;
}
const guards = load('karenGuards.ts');
const evidence = load('../../karenEvidence.ts');
const questions = [
  'Zoek bij Eneco het verschil tussen een voorschotfactuur en een jaarafrekening.',
  'Zoek de regels voor onderhoud en periodieke controle van een gasketel in Wallonië. Wat is het verschil?',
  'What is Eneco? Search the web and cite your sources.',
];

for (const question of questions) test('real API seam overrides mistaken classifier: ' + question, async () => {
  let researches = 0, writerCalls = 0, widgetClassification;
  const events = [];
  const source = question.includes('Wallonië')
    ? { content: 'Entretien et contrôle périodique chaudière gaz en Wallonie', metadata: { title: 'Chaudière gaz', url: 'https://energie.wallonie.be/' } }
    : { content: 'Eneco voorschotfactuur en jaarafrekening', metadata: { title: 'Eneco', url: 'https://eneco.be/' } };
  const Api = load('api.ts', {
    './classifier': { classify: async () => ({ classification: { skipSearch: true, showCalculationWidget: true } }) },
    './researcher': { __esModule: true, default: class { async research(_, input) {
      researches++; assert.equal(input.classification.classification.skipSearch, false);
      return { searchFindings: [source] };
    } } },
    '@/lib/session': { __esModule: true, default: { createSession: () => ({}) } },
    './widgets': { WidgetExecutor: { executeAll: async input => { widgetClassification = input.classification; return []; } } },
    '@/lib/prompts/search/writer': { getWriterPrompt: context => context },
  }).default;
  await new Api().searchAsync({ emit: (...args) => events.push(args) }, {
    followUp: question, chatHistory: [], config: { sources: ['web'], mode: 'speed',
      llm: { async *streamText() { writerCalls++; yield { contentChunk: 'answer [1]' }; } },
    },
  });
  assert.equal(researches, 1);
  assert.equal(widgetClassification.classification.showCalculationWidget, false);
  assert.equal(events.find(e => e[1]?.type === 'searchResults')[1].data[0], source);
  assert.equal(writerCalls, question === questions[0] ? 0 : 1);
  if (question === questions[0]) {
    assert.equal(events.find(e => e[1]?.type === 'response')[1].data,
      'Bronnen gevonden; passagecontrole volgt.');
  }
});

test('guard preserves numeric calculations, opt-out and disabled web source', () => {
  const original = { classification: { skipSearch: true, showCalculationWidget: true } };
  assert.equal(guards.guardClassification(original, 'Bereken 100 - 90', ['web']).classification.showCalculationWidget, true);
  assert.equal(guards.guardClassification(original, 'Zoek niet op het web', ['web']).classification.skipSearch, true);
  assert.equal(guards.guardClassification(original, questions[0], []).classification.skipSearch, true);
});

test('real search action normalizes JSON-array strings before network lookup', async () => {
  let received;
  const action = load('researcher/actions/search/webSearch.ts', {
    './baseSearch': { executeSearch: async input => { received = input.queries; return []; } },
  }).default;
  await action.execute({ queries: '["Eneco", "Eneco energy", "Eneco plc"]' }, {
    session: { getBlock: () => ({}) }, mode: 'speed',
  });
  assert.deepEqual(Array.from(received), ['Eneco', 'Eneco energy', 'Eneco plc']);
});

test('invalid query arguments never reach search', async () => {
  let calls = 0;
  const action = load('researcher/actions/search/webSearch.ts', {
    './baseSearch': { executeSearch: async () => { calls++; return []; } },
  }).default;
  for (const queries of [null, {}, [], [''], ['valid', 42], '[bad JSON', '{"query":"x"}']) {
    const result = await action.execute({ queries }, { session: { getBlock: () => ({}) }, mode: 'speed' });
    assert.equal(result.results.length, 0);
  }
  assert.equal(calls, 0);
});

test('native arrays and one plain query remain supported and bounded', () => {
  assert.deepEqual(Array.from(guards.normalizeQueries('Eneco factuur')), ['Eneco factuur']);
  assert.deepEqual(Array.from(guards.normalizeQueries([' a ', 'b', 'c', 'd'])), ['a', 'b', 'c']);
});

test('Walloon boiler search keeps the region and French official terminology', async () => {
  let received;
  const action = load('researcher/actions/search/webSearch.ts', {
    './baseSearch': { executeSearch: async input => { received = input.queries; return []; } },
  }).default;
  await action.execute({ queries: ['gas boiler maintenance', 'periodic boiler check'] }, {
    question: 'Zoek de regels voor onderhoud en periodieke controle van een gasketel in Wallonië. Wat is het verschil?',
    session: { getBlock: () => ({}) }, mode: 'speed',
  });
  assert.deepEqual(Array.from(received), ['Wallonie entretien contrôle périodique chaudière gaz']);
});

test('scoped official pages survive embedding deduplication as distinct URLs', async () => {
  const urls = [
    'https://energie.wallonie.be/home/controle-periodique.html',
    'https://energie.wallonie.be/home/entretien-chaudieres.html',
  ];
  const base = load('researcher/actions/search/baseSearch.ts', {
    '@/lib/searxng': { searchSearxng: async () => ({ results: [], suggestions: [] }) },
    '@/lib/utils/computeSimilarity': { __esModule: true, default: () => 0.9 },
    '@/lib/scraper': { __esModule: true, default: class {} },
    '@/lib/utils/splitText': { splitText: text => [text] },
  });
  const results = await base.executeSearch({
    queries: ['Wallonie entretien contrôle périodique chaudière gaz'],
    question: 'Zoek onderhoud en periodieke controle van een gasketel in Wallonië.',
    mode: 'speed',
    search: async () => ({ results: urls.map((url, i) => ({
      title: i ? 'Entretien chaudière gaz Wallonie' : 'Contrôle périodique chaudière gaz Wallonie',
      content: i ? 'Entretien et contrôle chaudière gaz en Wallonie' : 'Entretien et contrôle périodique chaudière gaz en Wallonie',
      url,
    })), suggestions: [] }),
    researchBlock: { id: 'r', data: { subSteps: [] } },
    session: { updateBlock: () => {} },
    embedding: { embedText: async () => [[1, 1]] },
  });
  assert.deepEqual(Array.from(results, r => r.metadata.url), urls);
});
