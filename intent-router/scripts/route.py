"""Route customer messages and show why each decision was made.

    python -m scripts.route --backend gemma                       # interactive: type messages, empty line or q quits
    python -m scripts.route --backend gemma --text "salio langu"  # one message

Dials (override config/router.json for this run only):
    --scoring max|topk_mean|centroid|logreg|mlp
                                       how intent scores are computed; loads that method's
                                       threshold/margin from config/router.json
    --k 5                              examples averaged per intent (topk_mean)
    --threshold 0.75 --margin 0.05     raise to send more to the LLM, lower to route more directly
    --no-guard                         switch off the action guard (question check on money-moving intents)
    --no-rules                         switch off the bank rule and the third-party statement rule
    --local-only                       gemma: load from the local cache only, never contact Hugging Face

Don't type sentences from data/examples/test.json: tuning by eye on the test set invalidates step 6.
"""

import argparse
import logging
import sys
from dataclasses import replace

from src.config import SCORING_METHODS, RouterConfig, load_router_config, load_settings, with_overrides
from src.embeddings import BACKENDS, QuotaExceededError
from src.logging_setup import setup_logging
from src.router import RouteDecision, Router, StaleIndexError

log = logging.getLogger("route")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Route messages and explain each decision.")
    parser.add_argument("--backend", choices=BACKENDS, required=True)
    parser.add_argument("--dim", type=int, help="vector size of the index to use (default 768)")
    parser.add_argument("--scoring", choices=SCORING_METHODS)
    parser.add_argument("--k", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--margin", type=float)
    parser.add_argument("--no-guard", action="store_true", help="switch off the action guard")
    parser.add_argument("--no-rules", action="store_true", help="switch off the bank and statement rules")
    parser.add_argument("--local-only", action="store_true", help="gemma: never contact Hugging Face")
    parser.add_argument("--text", help="route one message and exit")
    return parser.parse_args()


def router_config_from(args: argparse.Namespace, base: RouterConfig) -> RouterConfig:
    overrides = {
        "k": args.k,
        "threshold": args.threshold,
        "margin": args.margin,
        "action_guard": False if args.no_guard else None,
        "rules": False if args.no_rules else None,
    }
    return replace(base, **{key: value for key, value in overrides.items() if value is not None})


def format_decision(d: RouteDecision) -> str:
    lines = [
        f"\n  ROUTE: {d.route.upper():<8} intent: {d.intent}   score {d.score:.3f}   margin {d.margin:.3f}",
        "",
        "  Top intents:",
        *(f"    {score:.3f}  {intent}" for intent, score in d.top3),
        "",
        "  Nearest training examples:",
        *(f"    {score:.3f}  {intent:<18} {text!r}" for text, intent, score in d.nearest_examples),
        "",
        "  Why:",
        *(f"    - {reason}" for reason in d.reasons),
        "",
        f"  {d.latency_ms:.0f} ms",
    ]
    return "\n".join(lines)


def describe(config: RouterConfig, backend: str) -> str:
    scoring = f"{config.scoring} (k={config.k})" if config.scoring == "topk_mean" else config.scoring
    guard = "on" if config.action_guard else "OFF"
    return (
        f"backend {backend} | scoring {scoring} | threshold {config.threshold:.2f} "
        f"| margin {config.margin:.2f} | action guard {guard}"
    )


def route_and_print(router: Router, text: str) -> bool:
    """Route one message and print the decision. Returns False if the run should stop."""
    try:
        print(format_decision(router.route(text)))
    except QuotaExceededError as e:
        log.error("STOPPED: %s", e)
        return False
    return True


def interactive(router: Router) -> None:
    print("\nType a message (empty line or q to quit).")
    while True:
        try:
            text = input("\nmessage> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if text in ("", "q"):
            return
        if not route_and_print(router, text):
            return


def main() -> int:
    setup_logging()
    args = parse_args()
    settings = with_overrides(load_settings(), dim=args.dim, gemma_local_only=args.local_only or None)
    base = load_router_config(settings.paths.router_config, args.backend, args.scoring)
    config = router_config_from(args, base)

    try:
        router = Router(args.backend, settings, config)
    except StaleIndexError as e:
        log.error("CANNOT START: %s", e)
        return 1
    print(describe(config, args.backend))

    if args.text:
        return 0 if route_and_print(router, args.text) else 2
    interactive(router)
    return 0


if __name__ == "__main__":
    sys.exit(main())
