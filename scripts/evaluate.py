import argparse
import json
import statistics
import time

from app import judge
from app.classifier import classify_injection
from app.injection import find_injection
from app.normalize import normalize_text
from app.pipeline import Action, screen_prompt

INPUT_PRICE_PER_M = 0.05
OUTPUT_PRICE_PER_M = 0.40

judge_usage = {"calls": 0, "input_tokens": 0, "output_tokens": 0}

def track_judge_usage():
    completions = judge._client.chat.completions
    original_create = completions.create

    def create(**kwargs):
        judge_usage["calls"] += 1
        response = original_create(**kwargs)
        if response.usage:
            judge_usage["input_tokens"] += response.usage.prompt_tokens
            judge_usage["output_tokens"] += response.usage.completion_tokens
        return response

    completions.create = create


def load_dataset(path):
    with open(path, encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def evaluate(rows):
    results = []
    for row in rows:
        normalized = normalize_text(row["text"])
        classifier = classify_injection(normalized)

        started = time.perf_counter()
        decision = screen_prompt(row["text"])
        elapsed_ms = (time.perf_counter() - started) * 1000

        results.append({
            **row,
            "regex": bool(find_injection(normalized)),
            "classifier": classifier.is_injection,
            "pipeline": decision.action == Action.BLOCK,
            "judged": decision.judge is not None,
            "judge_error": decision.judge is not None and decision.judge.error is not None,
            "ms": elapsed_ms,
        })
    return results


def fraction(results, label, layer):
    subset = [r for r in results if r["label"] == label]
    hits = sum(r[layer] for r in subset)
    return f"{hits}/{len(subset)} ({hits / len(subset):.0%})"

    # Print summary table for each evaluation layer
def report(results):
    print(f"\n{'Layer':<16}{'Attacks caught':>18}{'False positives':>18}") # Print header for the summary table
    for layer, name in [("regex", "regex only"), ("classifier", "classifier only"), ("pipeline", "full pipeline")]: # Iterate over each evaluation layer and print its results
        print(f"{name:<16}{fraction(results, 'attack', layer):>18}{fraction(results, 'benign', layer):>18}") # Print the results for the current evaluation layer

    # Print full pipeline results by category
    print("\nFull pipeline by category:")
    for label, category in sorted({(r["label"], r["category"]) for r in results}):
        subset = [r for r in results if r["label"] == label and r["category"] == category]
        blocked = sum(r["pipeline"] for r in subset)
        print(f"  {label:<7}{category:<19}{blocked}/{len(subset)} blocked")

    # Print screening latency statistics
    latencies = [r["ms"] for r in results]
    print(f"\nScreening latency: p50 {statistics.median(latencies):.0f} ms, " # Print the screening latency median
          f"p95 {statistics.quantiles(latencies, n=20)[-1]:.0f} ms, max {max(latencies):.0f} ms") # Print the screening latency p95 and max values

    cost = (judge_usage["input_tokens"] * INPUT_PRICE_PER_M + judge_usage["output_tokens"] * OUTPUT_PRICE_PER_M) / 1_000_000
    errors = sum(r["judge_error"] for r in results)
    print(f"Judge: {judge_usage['calls']} calls ({errors} errors), "
          f"{judge_usage['input_tokens']} in / {judge_usage['output_tokens']} out tokens, "
          f"${cost:.4f} total, ${cost / len(results) * 1000:.2f} per 1k requests")

    print("\nMissed attacks:")
    for r in results:
        if r["label"] == "attack" and not r["pipeline"]:
            print(f"  [{r['category']}] {r['text'][:80]!r}")
    print("\nFalse positives:")
    for r in results:
        if r["label"] == "benign" and r["pipeline"]:
            print(f"  [{r['category']}] {r['text'][:80]!r}")


def main():
    parser = argparse.ArgumentParser(description="Evaluate the guardrail on a labelled dataset.")
    parser.add_argument("--data", default="data/redteam.jsonl")
    args = parser.parse_args()

    if classify_injection("warm-up") is None:
        raise SystemExit("Classifier unavailable: pip install -r requirements-ml.txt")
    track_judge_usage()
    report(evaluate(load_dataset(args.data)))


if __name__ == "__main__":
    main()