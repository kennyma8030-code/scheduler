"""Run every test module:

    python -m backend.class_scheduler.tests
"""

from __future__ import annotations

import importlib

MODULES = ["test_engine", "test_poll"]


def main() -> None:
    total = failures = 0
    for name in MODULES:
        module = importlib.import_module(f"{__package__}.{name}")
        print(f"=== {name}")
        tests = [(n, f) for n, f in sorted(vars(module).items())
                 if n.startswith("test_") and callable(f)]
        for test_name, fn in tests:
            total += 1
            try:
                fn()
                print(f"  ok    {test_name}")
            except AssertionError as exc:
                failures += 1
                print(f"  FAIL  {test_name}: {exc}")
            except Exception as exc:  # noqa: BLE001 — report, keep running
                failures += 1
                print(f"  ERROR {test_name}: {type(exc).__name__}: {exc}")
    print(f"\n{total - failures}/{total} passed")
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
