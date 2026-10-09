"""Three direct public searches; no model, retries, or production changes."""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import dotenv_values


def main():
    key = os.getenv("TAVILY_API_KEY")
    for path in (Path('.env'), Path('.env.local'), Path('experiments/karen_vane/.env')):
        if not key and path.exists():
            key = dotenv_values(path).get('TAVILY_API_KEY')
    if not key:
        raise SystemExit('TAVILY_API_KEY missing; no requests sent')
    cases = json.loads(Path(__file__).with_name('regression_questions.json').read_text())
    output = Path('output/karen-vane/tavily-direct-2026-10-03.jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Preserve evidence and avoid accidentally repeating billable requests.
    with output.open('x') as file, httpx.Client(timeout=30) as client:
        for case in cases:
            payload = dict(query=case['question'], search_depth='basic',
                           max_results=5, topic='general', country='belgium',
                           include_answer=False, include_raw_content=False,
                           auto_parameters=False, include_usage=True)
            started = time.monotonic()
            try:
                response = client.post('https://api.tavily.com/search', json=payload,
                                       headers={'Authorization': f'Bearer {key}'})
            except httpx.RequestError as error:
                print(f"{case['id']}: transport error {type(error).__name__}; stopped")
                break
            record = {**case, 'checked_at': datetime.now(timezone.utc).isoformat(),
                      'seconds': round(time.monotonic()-started, 2),
                      'http_status': response.status_code, 'parameters': payload}
            if response.is_success:
                data = response.json()
                record.update(results=data.get('results', []), usage=data.get('usage'),
                              request_id=data.get('request_id'))
            file.write(json.dumps(record, ensure_ascii=False)+'\n')
            file.flush()
            print(case['id'], record['http_status'], record['seconds'],
                  'seconds', len(record.get('results', [])), 'results', record.get('usage'), flush=True)
            if not response.is_success:
                print('Stopped after API failure; no retry')
                break


if __name__ == '__main__':
    main()
