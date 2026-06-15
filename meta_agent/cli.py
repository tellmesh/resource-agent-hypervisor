from __future__ import annotations

import argparse

from meta_agent.cli_commands import cmd_generate, cmd_pipeline, cmd_plan, cmd_repair, cmd_validate, cmd_verify


def main() -> int:
    parser = argparse.ArgumentParser(description="Meta-agent for creating, repairing, validating and generating resource agents.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="Create YAML proposal from natural-language prompt")
    plan.add_argument("prompt")
    plan.add_argument("--out", default=None)

    validate = sub.add_parser("validate", help="Validate an agent YAML spec")
    validate.add_argument("spec")

    repair = sub.add_parser("repair", help="Repair common errors in agent YAML spec")
    repair.add_argument("spec")
    repair.add_argument("--write", action="store_true")

    generate = sub.add_parser("generate", help="Validate, optionally repair and generate agent")
    generate.add_argument("spec")
    generate.add_argument("--no-repair", action="store_true")

    pipeline = sub.add_parser("pipeline", help="Prompt -> YAML -> validate/repair -> generate -> verify")
    pipeline.add_argument("prompt")
    pipeline.add_argument("--out", default=None)
    pipeline.add_argument("--no-repair", action="store_true")

    sub.add_parser("verify", help="Verify generated agents against contract hash")

    args = parser.parse_args()
    if args.cmd == "plan":
        return cmd_plan(args.prompt, args.out)
    if args.cmd == "validate":
        return cmd_validate(args.spec)
    if args.cmd == "repair":
        return cmd_repair(args.spec, write=args.write)
    if args.cmd == "generate":
        return cmd_generate(args.spec, auto_repair=not args.no_repair)
    if args.cmd == "pipeline":
        return cmd_pipeline(args.prompt, args.out, auto_repair=not args.no_repair)
    if args.cmd == "verify":
        return cmd_verify()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
