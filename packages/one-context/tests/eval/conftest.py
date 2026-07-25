"""Shared fixtures for eval tests.

Provides a `git_repo_root` factory: a fresh git repo with files committed
on HEAD so `git archive HEAD` works (used by sandbox tests).

Also auto-stubs `model_profiles.resolve_settings_path` so runner-driving
tests don't depend on `~/.claude/settings.*` files existing on the host
or carrying a specific `env.ANTHROPIC_MODEL` value.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_model_profiles: opt out of the autouse model-profile stub "
        "(use when the test exercises model resolution itself)",
    )


@pytest.fixture(autouse=True)
def _stub_model_profile_resolution(
    request: pytest.FixtureRequest,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stub `model_profiles.resolve_settings_path` for all eval tests.

    Runner (Stage 2.X.6) resolves `scenario.provider.model` against a
    fixed enum (claude-4.7 / kimi-2.5 / kimi-2.6 / glm-5 / glm-5.1) and
    reads the resulting settings.json for `env.ANTHROPIC_MODEL`. Test
    fixtures use a sentinel `model: m`, so without this stub every
    runner-driving test would raise `RuntimeError: cannot resolve model
    profile`. Point the resolver at a per-test temp settings.json
    carrying a fake `ANTHROPIC_MODEL` so `resolve_effective_model` also
    returns deterministically.

    Tests that exercise the resolver itself can opt out via
    `@pytest.mark.real_model_profiles`.

    Runner imports `resolve_settings_path` inside the function body, so
    monkeypatching the module attribute is picked up at call time.
    """
    if request.node.get_closest_marker("real_model_profiles"):
        return

    stub_path = tmp_path / "_stub_settings.json"
    stub_path.write_text(
        '{"env": {"ANTHROPIC_MODEL": "stub-model-for-tests"}}',
        encoding="utf-8",
    )

    from one_context.eval import model_profiles
    monkeypatch.setattr(
        model_profiles,
        "resolve_settings_path",
        lambda model_name: str(stub_path),
    )


@pytest.fixture()
def git_repo_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Init a fresh repo, commit a few sample tracked files, return root.

    Also redirects /tmp for sandbox.prepare via ONECXT_EVAL_TMP_ROOT.
    """
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(root), check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(root), check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=str(root), check=True,
    )

    (root / "README.md").write_text("hi", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "agents").mkdir()
    (root / ".claude" / "agents" / "dev.md").write_text("# Dev", encoding="utf-8")

    skills = root / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# demo", encoding="utf-8")

    feat = root / "features" / "x" / "y"
    feat.mkdir(parents=True)
    (feat / "spec.md").write_text("---\nid: y\n---\n\nbody", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=str(root), check=True,
    )

    # Redirect sandbox tmp root inside the test workdir
    sandbox_tmp = tmp_path / "sb-tmp"
    sandbox_tmp.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sandbox_tmp))
    return root
