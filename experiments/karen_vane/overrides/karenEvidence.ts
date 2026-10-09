/** Conservative source selection before Vane's writer in the isolated trial. */
import relations from './karenSourceRelations.json';
import { Chunk } from './types';

type Region = keyof typeof relations.regions;
const walloonEnergy = (question: string) =>
  /(?<!\p{L})(?:walloni[eë]|waals\w*|walloon|wallonia)(?!\p{L})/iu.test(question)
  && /ketel|chaudi|boiler|\bgas\b|gaz|elektric|stroom|électric/i.test(question);
const regionWords: Record<Region, RegExp> = {
  wallonia: /(?<!\p{L})(?:walloni[eë]|waals\w*|walloon|wallonia)(?!\p{L})/iu,
  brussels: /(?<!\p{L})(?:brussel\w*|bruxelles|brussels)(?!\p{L})/iu,
  flanders: /(?<!\p{L})(?:vlaander\w*|vlaams\w*|flanders|flemish)(?!\p{L})/iu,
};
const domainMatches = (host: string, domains: string[]) =>
  domains.some(domain => host === domain || host.endsWith('.' + domain));

export function authorityDomains(question: string): string[] {
  const regions = (Object.keys(regionWords) as Region[])
    .filter(region => regionWords[region].test(question));
  if (regions.length > 1 || /\bniet\s+(?:in\s+)?(?:walloni[eë]|vlaander\w*|brussel\w*|bruxelles)/i.test(question)) return [];
  const supplier = /\beneco\b/i.test(question);
  // A question naming both a supplier and a region needs a richer authority
  // relation than this pilot map. Do not guess a combined domain filter.
  if (regions.length && supplier) return [];
  return regions.length ? (regions[0] === 'wallonia' && walloonEnergy(question)
    ? relations.energy_regions.wallonia : relations.regions[regions[0]]) :
    supplier ? relations.suppliers.eneco : [];
}

export function selectEvidence(question: string, findings: Chunk[]): Chunk[] {
  const regions = (Object.keys(regionWords) as Region[])
    .filter(region => regionWords[region].test(question));
  const negated = /\bniet\s+(?:in\s+)?(?:walloni[eë]|vlaander\w*|brussel\w*|bruxelles)/i.test(question);
  if (regions.length > 1 || negated) return [];
  const region = regions[0];
  const supplier = /\beneco\b/i.test(question) ? 'eneco' : null;
  const topic = /factuur|afrekening|voorschot|invoice|\bbill\b/i.test(question) ?
    /factuur|afrekening|voorschot|invoice|bill/i :
    /ketel|verwarm|chaudi|boiler/i.test(question) ? /ketel|chaudi|boiler/i : null;
  const asksMaintenanceAndControl = /onderhoud|entretien/i.test(question)
    && /controle|contrôle|inspection/i.test(question);
  const energy = /\bgas\b|gasketel|chaudi/i.test(question) ? /gas|gaz/i :
    /elektric|stroom|électric/i.test(question) ? /elektric|stroom|électric|electric/i : null;

  return findings.filter(finding => {
    let url: URL;
    try { url = new URL(finding.metadata.url); } catch { return false; }
    if (url.protocol !== 'https:') return false;
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    if (region && !domainMatches(host, region === 'wallonia' && walloonEnergy(question)
      ? relations.energy_regions.wallonia : relations.regions[region])) return false;
    if (supplier && !domainMatches(host, relations.suppliers.eneco)) return false;
    const passage = finding.metadata.title + ' ' + finding.content;
    const walloonGasBoilerComparison = region === 'wallonia' && asksMaintenanceAndControl
      && /\bgas\b|gasketel|gaz/i.test(question) && /ketel|chaudi|boiler/i.test(question);
    const boilerPage = /ketel|chaudi|boiler/i.test(finding.metadata.title + ' ' + url.pathname);
    if (walloonGasBoilerComparison && !boilerPage) return false;
    if (region) {
      const mentioned = (Object.keys(regionWords) as Region[])
        .filter(candidate => regionWords[candidate].test(passage));
      if (mentioned.length && !mentioned.includes(region)) return false;
    }
    if (topic && !topic.test(passage)) return false;
    // Tavily's short snippet may omit "gaz" on an otherwise directly relevant
    // official boiler page. Keep it as a candidate, not as a verified answer.
    if (energy && !energy.test(passage) && !(walloonGasBoilerComparison && boilerPage)) return false;
    if (asksMaintenanceAndControl && (!/onderhoud|entretien/i.test(passage)
      || !/controle|contrôle|inspection/i.test(passage))) return false;
    return true;
  });
}

export function isEnecoInvoice(question: string): boolean {
  return /\beneco\b/i.test(question) && /voorschot|advance/i.test(question)
    && /afrekening|settlement/i.test(question);
}

/** Keep distinct Belgian supplier pages before embedding-based deduplication. */
export function selectInvoiceEvidence(question: string, findings: Chunk[]): Chunk[] {
  if (!isEnecoInvoice(question)) return findings;
  const selected = selectEvidence(question, findings).filter(finding => {
    try {
      const host = new URL(finding.metadata.url).hostname.toLowerCase();
      return (host === 'eneco.be' || host.endsWith('.eneco.be'))
        && /afrekening|voorschotfactuur/i.test(finding.metadata.url);
    } catch { return false; }
  });
  const priority = (url: string) =>
    /alles-over-je-afrekening-van-energie/i.test(url) ? 3 :
    /alle-info-over-je-voorschotfactuur/i.test(url) ? 2 :
    /afrekening|voorschotfactuur/i.test(url) ? 1 : 0;
  selected.sort((a, b) => priority(b.metadata.url) - priority(a.metadata.url));
  const seen = new Set<string>();
  return selected.filter(finding => {
    const url = finding.metadata.url.replace(/\/$/, '');
    if (seen.has(url)) return false;
    seen.add(url);
    return true;
  }).slice(0, 5).map(finding => ({
    content: finding.content,
    metadata: { title: finding.metadata.title, url: finding.metadata.url },
  }));
}

/** Preserve separate official URLs before semantic deduplication can merge them. */
export function selectScopedEvidence(question: string, findings: Chunk[]): Chunk[] {
  if (!authorityDomains(question).length) return [];
  const seen = new Set<string>();
  return selectEvidence(question, findings).filter(finding => {
    const url = finding.metadata.url.replace(/\/$/, '');
    if (seen.has(url)) return false;
    seen.add(url);
    return true;
  }).slice(0, 20).map(finding => ({
    content: finding.content,
    metadata: { title: finding.metadata.title, url: finding.metadata.url },
  }));
}
