from __future__ import annotations

import argparse
import getpass
from pathlib import Path

from patchpilot.agent import AgentLoop
from patchpilot.credentials import CredentialManager
from patchpilot.guardrails import GuardrailPolicy
from patchpilot.llm import MockLLM
from patchpilot.memory import MemoryStore
from patchpilot.models import Action
from patchpilot.tools import ToolDispatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="patchpilot")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run")
    run.add_argument("--task", required=True)
    run.add_argument("--test-cmd", required=True)
    run.add_argument("--max-steps", type=int, default=5)
    run.add_argument("--workspace", type=Path, default=Path.cwd())
    run.add_argument("--interactive-approval", action="store_true")

    auth = commands.add_parser("auth")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True)
    auth_commands.add_parser("status")
    auth_commands.add_parser("set")
    auth_commands.add_parser("clear")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    if args.command == "auth":
        return _run_auth(args)
    return _run_agent(args)


def _run_auth(args: argparse.Namespace) -> int:
    manager = CredentialManager()
    if args.auth_command == "status":
        print("configured" if manager.status() else "not configured")
    elif args.auth_command == "set":
        manager.set_key(getpass.getpass("OpenAI API key: "))
        print("configured")
    else:
        manager.clear()
        print("cleared")
    return 0


def _run_agent(args: argparse.Namespace) -> int:
    workspace = args.workspace.resolve()
    guardrails = GuardrailPolicy(workspace, interactive_approval=args.interactive_approval)
    memory = MemoryStore(workspace / ".patchpilot" / "memory.jsonl")
    dispatcher = ToolDispatcher(workspace, guardrails, memory)
    llm = MockLLM([Action("run_tests", {"command": args.test_cmd})])
    status = AgentLoop(llm, dispatcher, max_steps=args.max_steps).run(args.task, args.test_cmd)
    print(status.reason)
    return 0 if status.ok else 1
