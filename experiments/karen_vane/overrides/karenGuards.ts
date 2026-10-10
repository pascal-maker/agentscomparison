/** Narrow safeguards for the isolated Karen trial, not factual validation. */
export function explicitWebLookup(question: string): boolean {
  const text = question.toLowerCase();
  if (/\b(?:niet\s+(?:online\s+)?zoeken|zoek\s+niet|do\s+not\s+search|don['’]t\s+search)\b/.test(text)) return false;
  // A personal contract amount cannot be recovered from a public web page.
  if (/\b(?:mijn\s+eigen\s+contract|volgens\s+mijn\s+contract|wat\s+betaal\s+ik\s+precies)\b/.test(text)) return false;
  return /\b(?:zoek|opzoeken)\b|\b(?:search|look\s+up)\b.*\b(?:web|internet|online|sources)\b/i.test(text)
    || /\bwaar\s+(?:kan\s+ik|vind\s+ik)\b.{0,120}\b(?:nakijken|vinden|terugvinden)\b/.test(text)
    || /\bop\s+welke\s+offici[eë]le\b.{0,100}\b(?:vind\s+ik|staat|kan\s+ik)\b/.test(text);
}

export function numericCalculation(question: string): boolean {
  return (question.match(/\d+(?:[.,]\d+)?/g) || []).length >= 2
    && /[+*/×÷%]|\d\s*-\s*\d|\b(?:bereken|calculate|verschil|difference|plus|minus|maal|gedeeld)\b/i.test(question);
}

export function guardClassification<T extends { classification: { skipSearch: boolean; showCalculationWidget: boolean } }>(
  result: T, question: string, sources: string[],
): T {
  return { ...result, classification: { ...result.classification,
    skipSearch: sources.includes('web') && explicitWebLookup(question) ? false : result.classification.skipSearch,
    showCalculationWidget: result.classification.showCalculationWidget && numericCalculation(question),
  } };
}

export function normalizeQueries(value: unknown): string[] {
  let parsed = value;
  if (typeof parsed === 'string') {
    const text = parsed.trim();
    if (text.startsWith('[') || text.startsWith('{') || text.startsWith('"')) {
      try { parsed = JSON.parse(text); } catch { throw new Error('invalid_queries_json'); }
    } else parsed = text;
  }
  if (typeof parsed === 'string') parsed = [parsed];
  if (!Array.isArray(parsed) || !parsed.length || parsed.some(q => typeof q !== 'string' || !q.trim() || q.length > 1000)) {
    throw new Error('invalid_queries');
  }
  return [...new Set(parsed.map(q => q.trim()))].slice(0, 3);
}

/** Anchor explicit entity searches to the user's question, not an LLM paraphrase. */
export function planQueries(question: string | undefined, proposed: string[]): string[] {
  if (!question) return proposed;
  const wallonia = /(?:walloni[eë]|wallonia|waals\w*)/i.test(question);
  const negated = /\bniet\s+(?:in\s+)?(?:walloni[eë]|wallonia|vlaander\w*|brussel\w*|bruxelles)/i.test(question);
  const regions = [wallonia, /brussel\w*|bruxelles|brussels/i.test(question),
    /vlaander\w*|vlaams\w*|flanders/i.test(question)].filter(Boolean).length;
  if (negated || regions > 1) return [];
  if (regions === 1 && /vlaander\w*|vlaams\w*|flanders/i.test(question)
    && /maandpiek|capaciteitstarief/i.test(question)) {
    return ['Fluvius capaciteitstarief maandpiek digitale meter'];
  }
  if (/sociaal\s+tarief|tarif\s+social/i.test(question)
    && /geldigheidsperiode|huidig|kwartaal|trimestre|période/i.test(question)
    && /\bgas\b|aardgas|\bgaz\b/i.test(question)) {
    return [`CREG sociaal tarief voor energie aardgas ${new Date().getUTCFullYear()} kwartaal`];
  }
  if (wallonia && /ketel|chaudi|boiler/i.test(question) && /\bgas\b|gasketel|gaz/i.test(question)) {
    return ['Wallonie entretien contrôle périodique chaudière gaz'];
  }
  if (regions === 1 || /\beneco\b/i.test(question)) return [question];
  return proposed;
}

export function trace(stage: string, details: Record<string, unknown>): void {
  if (process.env.KAREN_VANE_DIAGNOSTICS === '1') {
    console.info('[karen-vane]', JSON.stringify({ stage, ...details }));
  }
}
