#!/usr/bin/env python3
"""Unified CLI for Akribeia. Zero runtime dependencies.

    akribeia gate   --contract CONTRACT --payload PAYLOAD [--baseline-payload B] [--json]
    akribeia trace  SESSIONS_DIR [--since YYYY-MM-DD] [--markdown]
    akribeia power  [--seed 42] [--trials 1000] [--markdown]
    akribeia audit  [--selftest]
    akribeia report [--write | --check]

Every subcommand delegates to the module that owns the logic and forwards its
exit code, so CI can use either this entry point or the script directly.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# subcommand -> (module name, one-line description)
COMMANDS: dict[str, tuple[str, str]] = {
    "gate": ("payload_gate", "verify a serialized provider payload against a contract"),
    "trace": ("analyze_traces", "privacy-safe telemetry from local JSONL session traces"),
    "power": ("nof1_power", "N-of-1 autocorrelation and statistical power simulator"),
    "audit": ("audit", "validate ledgers, cross-references, and secret/path hygiene"),
    "report": ("report", "render or check reports/ledger.md"),
}


def usage() -> str:
    width = max(len(name) for name in COMMANDS)
    lines = [
        "usage: akribeia <command> [args...]",
        "",
        "commands:",
    ]
    lines += [f"  {name.ljust(width)}  {desc}" for name, (_, desc) in COMMANDS.items()]
    lines += [
        "",
        "Run 'akribeia <command> --help' for the arguments of one command.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help", "help"}:
        print(usage())
        return 0
    name, rest = args[0], args[1:]
    if name not in COMMANDS:
        print(f"akribeia: unknown command {name!r}\n\n{usage()}", file=sys.stderr)
        return 2
    module_name, _ = COMMANDS[name]
    module = importlib.import_module(module_name)
    sys.argv = [f"akribeia {name}"] + rest
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
