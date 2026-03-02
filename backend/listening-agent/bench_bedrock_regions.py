"""
Quick benchmark: Bedrock ap-south-1 (Mumbai) vs us-east-1 (Virginia).
Fires both regions concurrently and logs latency metrics.

Usage:
    uv run python bench_bedrock_regions.py
"""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.config import Config

# MODEL_ID = "arn:aws:bedrock:ap-south-1:144918211563:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"
MODEL_ID = "arn:aws:bedrock:us-east-1:144918211563:inference-profile/global.anthropic.claude-haiku-4-5-20251001-v1:0"

BODY = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Say hello in one sentence."}],
    "temperature": 0,
})

CONFIG = Config(
    retries={"max_attempts": 1, "mode": "standard"},
    read_timeout=15,
    connect_timeout=5,
)

REGIONS = {
    "mumbai": "ap-south-1",
    "virginia": "us-east-1",
}

RUNS = 3  # number of rounds


def call_region(label: str, region: str) -> dict:
    """Synchronous Bedrock call with timing."""
    client = boto3.client("bedrock-runtime", region_name=region, config=CONFIG)

    t_start = time.perf_counter()
    response = client.invoke_model_with_response_stream(
        modelId=MODEL_ID,
        body=BODY,
        contentType="application/json",
    )

    t_first_token = None
    token_count = 0
    accumulated = ""

    for event in response["body"]:
        chunk = json.loads(event["chunk"]["bytes"])
        if chunk.get("type") == "content_block_delta":
            if t_first_token is None:
                t_first_token = time.perf_counter()
            delta_text = chunk.get("delta", {}).get("text", "")
            accumulated += delta_text
            token_count += 1

    t_end = time.perf_counter()

    ttft_ms = int((t_first_token - t_start) * 1000) if t_first_token else -1
    e2e_ms = int((t_end - t_start) * 1000)
    gen_ms = int((t_end - t_first_token) * 1000) if t_first_token else -1

    return {
        "label": label,
        "region": region,
        "ttft_ms": ttft_ms,
        "generation_ms": gen_ms,
        "e2e_ms": e2e_ms,
        "tokens": token_count,
        "response": accumulated.strip()[:80],
    }


async def bench_round(round_num: int, executor: ThreadPoolExecutor) -> list[dict]:
    """Fire both regions concurrently and return results."""
    loop = asyncio.get_event_loop()

    tasks = [
        loop.run_in_executor(executor, call_region, label, region)
        for label, region in REGIONS.items()
    ]
    results = await asyncio.gather(*tasks)

    print(f"\n{'='*70}")
    print(f"  Round {round_num}")
    print(f"{'='*70}")
    for r in results:
        print(
            f"  [{r['label']:>8}] ({r['region']:>12})"
            f"  TTFT={r['ttft_ms']:>5}ms"
            f"  gen={r['generation_ms']:>5}ms"
            f"  e2e={r['e2e_ms']:>5}ms"
            f"  tokens={r['tokens']}"
        )

    return list(results)


async def main():
    print("Bedrock Region Benchmark: Mumbai vs Virginia")
    print(f"Model: {MODEL_ID.split('/')[-1]}")
    print(f"Rounds: {RUNS}")

    executor = ThreadPoolExecutor(max_workers=2)
    all_results: dict[str, list[dict]] = {label: [] for label in REGIONS}

    for i in range(1, RUNS + 1):
        results = await bench_round(i, executor)
        for r in results:
            all_results[r["label"]].append(r)

    # Summary
    print(f"\n{'='*70}")
    print("  SUMMARY (averages)")
    print(f"{'='*70}")
    for label, runs in all_results.items():
        avg_ttft = sum(r["ttft_ms"] for r in runs) // len(runs)
        avg_gen = sum(r["generation_ms"] for r in runs) // len(runs)
        avg_e2e = sum(r["e2e_ms"] for r in runs) // len(runs)
        print(
            f"  [{label:>8}]"
            f"  avg TTFT={avg_ttft:>5}ms"
            f"  avg gen={avg_gen:>5}ms"
            f"  avg e2e={avg_e2e:>5}ms"
        )

    # Delta
    m = all_results["mumbai"]
    v = all_results["virginia"]
    ttft_delta = (sum(r["ttft_ms"] for r in m) // len(m)) - (sum(r["ttft_ms"] for r in v) // len(v))
    e2e_delta = (sum(r["e2e_ms"] for r in m) // len(m)) - (sum(r["e2e_ms"] for r in v) // len(v))
    faster = "mumbai" if e2e_delta < 0 else "virginia"
    print(f"\n  Delta: TTFT={ttft_delta:+d}ms  e2e={e2e_delta:+d}ms  (negative = mumbai faster)")
    print(f"  Winner (e2e): {faster}")

    executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
