#!/usr/bin/env python3
"""Supervised local-only smoke test for one bundled slim recipe.

This helper loads the integration's device wrapper directly, without starting
Home Assistant. It never contacts Joyami, Google, or any Mi cloud service.

Examples:
    .venv/bin/python tools/smoke_test_recipe.py --list
    .venv/bin/python tools/smoke_test_recipe.py \
        --host 192.168.69.206 --token "$TOKEN" --info
    .venv/bin/python tools/smoke_test_recipe.py \
        --host 192.168.69.206 --token "$TOKEN" --read
    .venv/bin/python tools/smoke_test_recipe.py \
        --host 192.168.69.206 --token "$TOKEN" --recipe 4209 --start --confirm
    .venv/bin/python tools/smoke_test_recipe.py \
        --host 192.168.69.206 --token "$TOKEN" --next --observe 5
    .venv/bin/python tools/smoke_test_recipe.py \
        --host 192.168.69.206 --token "$TOKEN" --cancel

Only --start sends a cooking command. Keep a pot on the cooker and stay nearby.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "chunmi_ihcooker_slim"
RECIPES_FILE = COMPONENT / "recipes.json"
PACKAGE = "chunmi_smoke_test_pkg"


def _load_module(name: str) -> types.ModuleType:
    """Load one integration module without importing its HA-dependent package."""
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", COMPONENT / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE}.{name}"] = module
    spec.loader.exec_module(module)
    return module


def _load_device_module():
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(COMPONENT)]
    sys.modules[PACKAGE] = package
    _load_module("const")
    _load_module("recipe")
    return _load_module("device")


def _load_recipes() -> list[dict]:
    recipes = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    if not isinstance(recipes, list):
        raise RuntimeError("recipes.json must contain a list")
    return recipes


def _resolve_recipe(recipes: list[dict], value: str) -> dict:
    needle = value.strip()
    matches = [
        item
        for item in recipes
        if str(item.get("id")) == needle
        or needle in (str(item.get("name_zh") or ""), str(item.get("name_en") or ""))
    ]
    if not matches:
        raise SystemExit(f"Unknown recipe: {value!r}; use --list to see IDs")
    if len(matches) > 1:
        raise SystemExit(
            "Ambiguous recipe; use its numeric ID: "
            + ", ".join(str(item["id"]) for item in matches)
        )
    return matches[0]


def _device(args: argparse.Namespace):
    if not args.host or not args.token:
        raise SystemExit("--host and --token are required for this action")
    module = _load_device_module()
    return module.IHCookerSlimDevice(
        args.host,
        args.token,
        timeout=args.timeout,
    )


def _print_recipe(recipe: dict) -> None:
    print(f"recipe:  {recipe['id']} {recipe['name_zh']} / {recipe['name_en']}")
    print(f"length:  {len(bytes.fromhex(recipe['runnable_cookcode']))} bytes")
    print(f"name:    {recipe['name_gbk']}")


def _print_state(values: dict) -> None:
    print("--- state ---")
    for key in (
        "status",
        "work_status",
        "cook_time",
        "pause_time",
        "phase",
        "recipe_type",
        "temperature",
        "menu",
    ):
        print(f"{key:<14} {values.get(key)!r}")


def _print_cooking_assessment(values: dict) -> None:
    active = values.get("status") in (1, 2, 3) or values.get("work_status") in (2, 10)
    print(f"active_cooking: {active}")
    if not active:
        print(
            "NOTE: the command was accepted, but the cooker reports idle. "
            "A panel press or an explicit 3/8 next_step may still be required "
            "to enter sustained cooking."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--list", action="store_true", help="List bundled recipes")
    action.add_argument("--info", action="store_true", help="Print miIO.info only")
    action.add_argument("--read", action="store_true", help="Read key properties")
    action.add_argument("--start", action="store_true", help="Start --recipe locally")
    action.add_argument("--next", action="store_true", help="Advance phase via MIoT 3/8")
    action.add_argument("--pause", action="store_true", help="Pause the current session")
    action.add_argument("--cancel", action="store_true", help="Cancel the current session")
    parser.add_argument("--host", help="Cooker IP address")
    parser.add_argument("--token", help="32-character miIO token")
    parser.add_argument("--timeout", type=int, default=5, help="UDP timeout in seconds")
    parser.add_argument("--recipe", default="4432", help="Recipe ID or exact name")
    parser.add_argument(
        "--observe",
        type=int,
        default=0,
        metavar="SECONDS",
        help="After --start, wait and print live state to confirm heating",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required with --start; confirms a supervised cooking test",
    )
    args = parser.parse_args()

    recipes = _load_recipes()

    if args.list:
        for recipe in recipes:
            print(f"{recipe['id']:>6}  {recipe['name_zh']}  /  {recipe['name_en']}")
        return 0

    if args.start and not args.confirm:
        raise SystemExit("Refusing to start cooking without --confirm")

    cooker = _device(args)

    if args.info:
        info = cooker.info()
        print(f"model:    {info.model}")
        print(f"mac:      {getattr(info, 'mac_address', getattr(info, 'mac', None))}")
        print(f"firmware: {info.firmware_version}")
        return 0

    if args.read:
        _print_state(cooker.read_properties())
        return 0

    if args.start:
        recipe = _resolve_recipe(recipes, args.recipe)
        _print_recipe(recipe)
        print("Starting over local miIO action 3/1 ...")
        result = cooker.start_cookcode(
            recipe["runnable_cookcode"], recipe["name_gbk"]
        )
        print(f"result: {result!r}")
        if args.observe:
            print(f"Observing for {args.observe}s to confirm heating ...")
            time.sleep(args.observe)
            observed = cooker.read_properties()
            _print_state(observed)
            _print_cooking_assessment(observed)
        print("Check the cooker display. Run --cancel when finished.")
        return 0

    if args.next:
        print(f"result: {cooker.next_step()!r}")
        if args.observe:
            print(f"Observing for {args.observe}s after next_step ...")
            time.sleep(args.observe)
            observed = cooker.read_properties()
            _print_state(observed)
            _print_cooking_assessment(observed)
        return 0

    if args.pause:
        print(f"result: {cooker.pause()!r}")
        return 0

    print(f"result: {cooker.cancel_cooking()!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
