"""one-context evaluation runner — `onecxt eval`.

Modules:
- sandbox: tmp dir prepare/teardown via `git archive`
- fixture: overlay-and-replace fixture into tmp dir
- artifacts: sha256 pre/post snapshot for artifact collection
- judge: spawn `claude -p` cheap haiku judge with caching
- report: render single-file HTML report (Jinja2 + inline CSS)
- skill_config / scenario_config: pydantic schemas
- runner: orchestrate one full eval run
"""

__all__ = [
    "runner",
    "sandbox",
    "fixture",
    "artifacts",
    "judge",
    "report",
    "skill_config",
    "scenario_config",
]
