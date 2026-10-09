import { searchSearxng } from './searxng';
import z from 'zod';
import { trace } from './agents/search/karenGuards';
import { authorityDomains, isEnecoInvoice } from './karenEvidence';

const responseSchema = z.object({
  results: z.array(z.object({
    title: z.string().min(1), content: z.string(),
    url: z.string().url().refine(url => /^https?:\/\//.test(url)),
  })),
  usage: z.object({ credits: z.number() }).optional(),
});

// Only the web_search action selects this adapter; other search tools stay unchanged.
export function searchWebForQuestion(question: string): typeof searchSearxng {
 return async (query, opts) => {
  const provider = process.env.KAREN_WEB_SEARCH_PROVIDER || 'searxng';
  if (provider === 'searxng') return searchSearxng(query, opts);
  if (provider !== 'tavily') throw new Error('Unknown web search provider');
  const key = process.env.TAVILY_API_KEY;
  if (!key) throw new Error('Tavily key missing');
  try {
    // Tavily's domain restriction displaced Eneco's invoice articles with a
    // tariff page in the live regression. The downstream authority gate still
    // accepts only Eneco's own Belgian invoice pages for this exact route.
    const domains = isEnecoInvoice(question) ? [] : authorityDomains(question);
    const response = await fetch('https://api.tavily.com/search', {
      method: 'POST', headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(15000),
      body: JSON.stringify({ query, search_depth: 'basic', auto_parameters: false,
        max_results: 5, topic: 'general', country: 'belgium',
        ...(domains.length ? { include_domains: domains, include_domains_mode: 'restrict' } : {}),
        include_answer: false, include_raw_content: false, include_usage: true }),
    });
    if (!response.ok) throw new Error('search failed');
    const data = responseSchema.parse(await response.json());
    trace('provider_results', { provider, query, count: data.results.length, credits: data.usage?.credits });
    return { results: data.results, suggestions: [] };
  } catch {
    // Do not expose response bodies, credentials, or fetch error details.
    throw new Error('Tavily search unavailable');
  }
 };
};

export const searchWeb: typeof searchSearxng = searchWebForQuestion('');
