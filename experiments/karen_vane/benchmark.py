"""Public questions only; saves observations, not automatic correctness scores."""

import argparse
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .adapter import PublicQuestion, Settings, VaneAdapter


async def run(args):
    cases = json.loads(Path(args.cases).read_text())
    if args.ids:
        wanted = set(args.ids.split(","))
        if wanted - {case["id"] for case in cases}:
            raise ValueError("Unknown case ID")
        cases = [case for case in cases if case["id"] in wanted]
    settings = Settings.from_env()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as client:
        adapter = VaneAdapter(client, settings)
        with output.open("w") as file:
            for case in cases:
                started = time.monotonic()
                answer = await adapter.answer(PublicQuestion(question=case["question"]))
                record = {
                    **case, "checked_at": datetime.now(timezone.utc).isoformat(),
                    "chat_model": settings.chat_model, "embedding_model": settings.embedding_model,
                    "seconds": round(time.monotonic() - started, 2),
                    "response": answer.model_dump(mode="json"), "human_review": "pending",
                }
                file.write(json.dumps(record, ensure_ascii=False) + "\n")
                file.flush()
                print(f"{case['id']}: {answer.status}, {record['seconds']}s, "
                      f"{len(answer.sources)} sources, error={answer.error_code}", flush=True)
                if answer.status == "service_error":
                    print("Stopped after service failure; diagnose before retrying remaining cases.", flush=True)
                    break


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default=str(Path(__file__).with_name("questions.json")))
    parser.add_argument("--ids", help="Comma-separated case IDs; default: all 20")
    parser.add_argument("--output", default="output/karen-vane/results.jsonl")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
