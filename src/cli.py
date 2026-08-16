import argparse
import asyncio

from src.agent.discovery import DiscoveryAgent
from src.agent.planners import MockPlanner, OpenAIPlanner, GeminiPlanner
from src.capabilities.store import load_artifact, save_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface


def parse_inputs(values):
    inputs = {}

    for item in values:
        if "=" not in item:
            raise ValueError(
                f"Invalid input '{item}'. Use key=value format, for example member_id=10042"
            )

        key, value = item.split("=", 1)
        inputs[key] = value

    return inputs


def get_planner(planner_name):
    if planner_name == "openai":
        return OpenAIPlanner()

    if planner_name == "gemini":
        return GeminiPlanner()

    return MockPlanner()


async def do_discover(args):
    planner = get_planner(args.planner)

    surface = PlaywrightSurface(
        headless=args.headless
    )

    agent = DiscoveryAgent(
        surface=surface,
        planner=planner,
    )

    artifact = await agent.run(
        args.goal,
        args.target,
    )

    save_artifact(
        artifact,
        args.artifact,
    )

    print("\nDiscovery completed successfully.\n")
    print(artifact.model_dump_json(indent=2))


async def do_replay(args):
    artifact = load_artifact(
        args.artifact
    )

    inputs = parse_inputs(
        args.input
    )

    surface = PlaywrightSurface(
        headless=args.headless
    )

    engine = ReplayEngine(
        surface
    )

    result = await engine.run(
        artifact,
        inputs,
    )

    print("\nReplay result:\n")
    print(result.model_dump_json(indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Computer-use automation system"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    # ---------------------------------------------------------
    # DISCOVERY COMMAND
    # ---------------------------------------------------------

    discover_parser = subparsers.add_parser(
        "discover",
        help="Run an LLM-driven discovery workflow",
    )

    discover_parser.add_argument(
        "--goal",
        required=True,
        help="Natural-language task for the agent",
    )

    discover_parser.add_argument(
        "--target",
        required=True,
        help="Target application URL",
    )

    discover_parser.add_argument(
        "--planner",
        choices=[
            "mock",
            "openai",
            "gemini",
        ],
        default="mock",
        help="Planner/model provider to use during discovery",
    )

    discover_parser.add_argument(
        "--artifact",
        default="artifacts/lookup_member_balance.json",
        help="Path where the generated capability artifact will be stored",
    )

    discover_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser without showing the browser window",
    )

    # ---------------------------------------------------------
    # REPLAY COMMAND
    # ---------------------------------------------------------

    replay_parser = subparsers.add_parser(
        "replay",
        help="Replay a saved capability without an LLM",
    )

    replay_parser.add_argument(
        "--artifact",
        required=True,
        help="Path to capability artifact JSON",
    )

    replay_parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Capability input in key=value format",
    )

    replay_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run the browser without showing the browser window",
    )

    args = parser.parse_args()

    if args.command == "discover":
        asyncio.run(
            do_discover(args)
        )

    elif args.command == "replay":
        asyncio.run(
            do_replay(args)
        )


if __name__ == "__main__":
    main()