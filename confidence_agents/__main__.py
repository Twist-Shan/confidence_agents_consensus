import argparse
import json
from pathlib import Path

from .experiment import plan, run
from .runtime import catalog


def main():
    p = argparse.ArgumentParser(description="Confidence allocation pilot; mock by default")
    p.add_argument("command", choices=["plan", "check-models", "run"])
    p.add_argument("--config", default="configs/pilot.json")
    p.add_argument("--models", nargs="+", help="Model keys, e.g. luna glm qwen")
    p.add_argument("--smoke", action="store_true", help="2 items, 1 root, 2 rounds, 4 local contexts, 1 repeat")
    p.add_argument("--backend", choices=["mock", "openrouter"], default="mock")
    p.add_argument("--out", default="runs/mock-smoke")
    p.add_argument("--max-requests", type=int, help="Total call-record limit, including already completed requests")
    args = p.parse_args()
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        if args.models:
            config["selected"] = args.models
        if args.smoke:
            config.update(items=2, roots_per_item=1, rounds=2, local_contexts=4, local_repeats=1)
        estimate = plan(config)
        if args.command == "plan":
            result = estimate
        elif args.command == "check-models":
            result = catalog({k: config["models"][k] for k in config["selected"]})
        else:
            if args.backend == "openrouter" and args.out == "runs/mock-smoke":
                p.error("Specify a separate --out directory for live data")
            print(json.dumps(estimate, indent=2))
            result = run(config, args.out, args.backend, args.max_requests)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        # Transport exceptions can include URLs: the key is sent only in a header.
        p.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
