#!/usr/bin/env python3
"""
health_check.py — проверка целостности модулей, конфигов и БД Argos.
"""

from __future__ import annotations

import importlib
import json
import os
import py_compile
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: str


def check_required_paths() -> List[CheckResult]:
    required = [
        "main.py",
        "src/core.py",
        "src/vision.py",
        "src/quantum/logic.py",
        "src/factory/replicator.py",
        "config/identity.json",
        "config/smart_systems.json",
        "data",
    ]

    results = []
    for rel in required:
        path = PROJECT_ROOT / rel
        results.append(CheckResult(
            name=f"path:{rel}",
            ok=path.exists(),
            details="found" if path.exists() else "missing",
        ))
    return results


def check_python_syntax() -> List[CheckResult]:
    py_files = sorted((PROJECT_ROOT / "src").rglob("*.py"))
    results = []

    for path in py_files:
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        try:
            py_compile.compile(str(path), doraise=True)
            results.append(CheckResult(f"syntax:{rel}", True, "ok"))
        except Exception as exc:
            results.append(CheckResult(f"syntax:{rel}", False, f"{type(exc).__name__}: {exc}"))

    return results


def check_runtime_imports() -> List[CheckResult]:
    modules = [
        "src.admin",
        "src.agent",
        "src.vision",
        "src.quantum.logic",
        "src.factory.replicator",
        "src.security.root_manager",
        "src.security.syscalls",
        "src.interface.argos_shell",
    ]

    results = []
    for module in modules:
        try:
            importlib.import_module(module)
            results.append(CheckResult(f"import:{module}", True, "ok"))
        except Exception as exc:
            results.append(CheckResult(f"import:{module}", False, f"{type(exc).__name__}: {exc}"))
    return results


def check_json_configs() -> List[CheckResult]:
    configs = [
        "config/identity.json",
        "config/smart_systems.json",
        "data/iot_devices.json",
    ]

    results = []
    for rel in configs:
        path = PROJECT_ROOT / rel
        if not path.exists():
            results.append(CheckResult(f"json:{rel}", False, "missing"))
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                json.load(f)
            results.append(CheckResult(f"json:{rel}", True, "valid"))
        except Exception as exc:
            results.append(CheckResult(f"json:{rel}", False, f"invalid: {exc}"))
    return results


def check_database() -> List[CheckResult]:
    db_path = PROJECT_ROOT / "data/argos.db"
    if not db_path.exists():
        return [CheckResult("db:data/argos.db", False, "missing")]

    results = []
    try:
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA integrity_check;")
            row = cur.fetchone()
            integrity = (row[0] if row else "unknown")
            results.append(CheckResult(
                "db:integrity_check",
                integrity == "ok",
                integrity,
            ))

            cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cur.fetchall()]
            results.append(CheckResult(
                "db:tables_present",
                len(tables) > 0,
                f"count={len(tables)}",
            ))
        finally:
            conn.close()
    except Exception as exc:
        results.append(CheckResult("db:open", False, f"{type(exc).__name__}: {exc}"))

    return results


def render(results: List[CheckResult]) -> int:
    ok_count = sum(1 for r in results if r.ok)
    fail_count = len(results) - ok_count

    print("ARGOS HEALTH CHECK")
    print("=" * 60)
    for r in results:
        status = "OK" if r.ok else "FAIL"
        print(f"[{status:4}] {r.name:<35} -> {r.details}")

    print("-" * 60)
    print(f"Summary: total={len(results)} ok={ok_count} fail={fail_count}")

    return 0 if fail_count == 0 else 1


def main() -> int:
    os.chdir(PROJECT_ROOT)
    all_results = []
    all_results.extend(check_required_paths())
    all_results.extend(check_python_syntax())
    all_results.extend(check_runtime_imports())
    all_results.extend(check_json_configs())
    all_results.extend(check_database())
    return render(all_results)


if __name__ == "__main__":
    sys.exit(main())
