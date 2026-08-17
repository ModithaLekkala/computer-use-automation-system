from __future__ import annotations

import argparse
import asyncio
import json

from src.agent.discovery import DiscoveryAgent
from src.agent.planners import GeminiPlanner, MockPlanner, OpenAIPlanner
from src.capabilities.store import load_artifact, save_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface


def parse_inputs(values: list[str]) -> dict:
    inputs = {}
    for item in values:
        if "=" not in item:
            raise ValueError(
                f"Invalid input {item!r}. Use key=value format."
            )
        key, value = item.split("=", 1)
        inputs[key] = value
    return inputs


def get_planner(name: str):
    if name == "openai":
        return OpenAIPlanner()
    if name == "gemini":
        return GeminiPlanner()
    return MockPlanner()


async def do_discover(args):
    planner = get_planner(args.planner)
    agent = DiscoveryAgent(
        surface=PlaywrightSurface(headless=args.headless),
        planner=planner,
    )
    artifact = await agent.run(args.goal, args.target)
    save_artifact(artifact, args.artifact)
    print("\nDiscovery completed successfully.\n")
    print(artifact.model_dump_json(indent=2))


async def do_replay(args):
    artifact = load_artifact(args.artifact)
    engine = ReplayEngine(
        PlaywrightSurface(headless=args.headless),
        evidence_dir=args.evidence_dir,
    )
    result = await engine.run(
        artifact,
        parse_inputs(args.input),
        enable_operator=not args.no_operator,
    )
    print("\nReplay result:\n")
    print(result.model_dump_json(indent=2))


async def do_handoff_demo(args):
    artifact = load_artifact(args.artifact)
    print(
        "\nHandoff demo starting.\n"
        "1. Wait for Chromium to show 'Manual Review Required'.\n"
        "2. Open http://127.0.0.1:8001\n"
        "3. Click 'Take Control'.\n"
        "4. In the SAME Chromium window click 'Continue After Review'.\n"
        "5. Return to the operator page and click 'Resume'.\n"
    )
    engine = ReplayEngine(
        PlaywrightSurface(headless=False),
        evidence_dir="evidence/handoff",
    )
    result = await engine.run(
        artifact,
        {"member_id": "10044"},
        enable_operator=True,
    )
    print(result.model_dump_json(indent=2))


async def do_recovery_demo(args):
    artifact = load_artifact(args.artifact)
    engine = ReplayEngine(
        PlaywrightSurface(headless=args.headless),
        evidence_dir="evidence/recovery",
    )
    result = await engine.run(
        artifact,
        {"member_id": "10045"},
        enable_operator=False,
    )
    print(result.model_dump_json(indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Computer-use automation system"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    d = sub.add_parser("discover")
    d.add_argument("--goal", required=True)
    d.add_argument("--target", required=True)
    d.add_argument(
        "--planner",
        choices=["mock", "openai", "gemini"],
        default="mock",
    )
    d.add_argument(
        "--artifact",
        default="artifacts/lookup_member_balance.json",
    )
    d.add_argument("--headless", action="store_true")

    r = sub.add_parser("replay")
    r.add_argument("--artifact", required=True)
    r.add_argument("--input", action="append", default=[])
    r.add_argument("--headless", action="store_true")
    r.add_argument("--no-operator", action="store_true")
    r.add_argument("--evidence-dir", default="evidence/replay")

    h = sub.add_parser("handoff-demo")
    h.add_argument(
        "--artifact",
        default="artifacts/lookup_member_balance.json",
    )

    rec = sub.add_parser("recovery-demo")
    rec.add_argument(
        "--artifact",
        default="artifacts/lookup_member_balance.json",
    )
    rec.add_argument("--headless", action="store_true")

    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(do_discover(args))
    elif args.command == "replay":
        asyncio.run(do_replay(args))
    elif args.command == "handoff-demo":
        asyncio.run(do_handoff_demo(args))
    elif args.command == "recovery-demo":
        asyncio.run(do_recovery_demo(args))


if __name__ == "__main__":
    main()
