"""End-to-end runner test using a mocked provider + replayed judge.

Builds a minimal git repo with a `skills/demo` skill + a scenario that
points at an in-tree feature subtree via `target_path`. We monkeypatch
`one_context.eval.provider.run_provider` to skip the JS provider, since
this is the ergonomic equivalent of "claude wrote the file" — the
artifact pipeline / judge / report still exercise the real code paths.

ISS-020 (Stage 2.0.2): cwd is single-source from the sandbox root; the
scenario's `target_path` says where to look, NOT where to spawn cc.
ISS-022 (Stage 2.0.3): legacy `fixture:` block is gone; fixtures live
in the repo and are picked up by sandbox.prepare via git archive.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from one_context.eval import provider as prov_mod
from one_context.eval import judge as J
from one_context.eval import runner as R


def _init_repo(tmp_path: Path, *, with_overlay_patch: bool = False) -> Path:
    """Build a tiny git repo with a `demo` skill and an in-tree fixture.

    When `with_overlay_patch` is True, the scenario also declares an
    `overlay.apply` entry that patches a single file in the fixture.
    """
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.email", "t@e"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(root), check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=str(root), check=True)

    # ── skill + eval.yaml + scenario ─────────────────────────────────
    skill = root / "skills" / "demo"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo", encoding="utf-8")
    (skill / "eval.yaml").write_text(
        "judge_model: m\n"
        "artifacts:\n"
        "  - production/out.md\n"
        "default_rubric: |\n"
        "  must produce production/out.md with non-empty body\n",
        encoding="utf-8",
    )

    scn = skill / "evals" / "case"
    scn.mkdir(parents=True)

    scenario_yaml = (
        "query: |\n"
        "  please write under {{ target_path }}\n"
        "target_path: features/foo/\n"
        "provider:\n"
        "  model: m\n"
        "  timeoutMs: 1000\n"
        "threshold: 0.5\n"
    )
    if with_overlay_patch:
        # write a single-file patch in the scenario dir so the overlay
        # snapshot has something concrete to assert on.
        (scn / "patch-spec.md").write_text(
            "PATCHED spec body for the scenario\n", encoding="utf-8",
        )
        scenario_yaml += (
            "overlay:\n"
            "  apply:\n"
            "    - src: ./patch-spec.md\n"
            '      dst: "{{ target_path }}spec.md"\n'
        )
    (scn / "scenario.yaml").write_text(scenario_yaml, encoding="utf-8")

    # ── in-tree fixture (picked up by `git archive HEAD`) ────────────
    feat = root / "features" / "foo" / "production"
    feat.mkdir(parents=True)
    (feat / "out.md").write_text("hello world body", encoding="utf-8")
    (feat.parent / "spec.md").write_text("---\n---\n\nspec body", encoding="utf-8")

    # ── provider script (mocked at the python layer) ─────────────────
    prov_dir = root / "evals" / "providers"
    prov_dir.mkdir(parents=True)
    (prov_dir / "claude-code.js").write_text("// mocked\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=str(root), check=True)
    return root


def test_runner_full_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _init_repo(tmp_path)

    # Redirect sandbox /tmp into the test workdir.
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    # Mock the provider: skip JS spawn entirely.
    captured: dict = {}

    def fake_run(**kwargs):
        cwd = kwargs["cwd"]
        # ISS-020: cwd is now the sandbox root (≡ repo root). The skill
        # is responsible for writing under target_path/.
        target = Path(cwd) / "features" / "foo" / "production" / "out.md"
        target.write_text("hello world body — modified by skill", encoding="utf-8")
        captured["cwd"] = str(cwd)
        captured["query"] = kwargs["query"]
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=10,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"] + "-20250901",
            final_text="I wrote out.md with the body.",
            tool_calls=[{"name": "Write", "input": {"file_path": str(target)}}],
            stream_path=str(kwargs["stream_path"]),
            timeout=False,
            stderr_tail="",
            raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)

    # Pre-record the judge replay file so judge.evaluate doesn't spawn claude.
    replay_dir = tmp_path / "judge-replay"
    replay_dir.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_JUDGE_REPLAY_DIR", str(replay_dir))

    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.95, "reason": "ok"}',
    )

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"
    run_json = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run_json["judge"]["pass"] is True
    assert run_json["judge"]["score"] == 0.95
    assert run_json["model_drift"] is True  # actual != requested
    assert any(a["path"] == "production/out.md" for a in run_json["artifacts"])
    # report.html exists
    assert outcome.report_html_path.is_file()

    # ISS-020 invariants:
    # (a) provider was spawned with cwd = sandbox root, NOT target_path subdir
    assert captured["cwd"].endswith(outcome.run_id)  # /tmp/onecxt-eval-<runId>
    # (b) `{{ target_path }}` placeholder in query was substituted
    assert "{{ target_path }}" not in captured["query"]
    assert "features/foo/" in captured["query"]
    # (c) run.json carries target_path + target_path_sha256
    assert run_json["target_path"] == "features/foo/"
    assert run_json["target_path_sha256"]  # non-empty hex
    assert len(run_json["target_path_sha256"]) == 64
    # (d) legacy `cwd` field mirrors target_path for backward compat
    assert run_json["cwd"] == "features/foo/"


def test_runner_skill_override_replaces_skill_and_records_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 2.6: --skill-override replaces sandbox `skills/<skill>/` and
    records {dir, sha256_per_file} in run.json (tech_design §10.5)."""
    root = _init_repo(tmp_path)
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    # Build the override dir: a candidate SKILL.md + a references file
    # + an eval.yaml that MUST be refused (§10.5: evaluation set is baseline).
    override_dir = tmp_path / "candidate"
    override_dir.mkdir()
    (override_dir / "SKILL.md").write_text(
        "# DEMO CANDIDATE\nrewritten skill body\n", encoding="utf-8",
    )
    (override_dir / "references").mkdir()
    (override_dir / "references" / "guide.md").write_text(
        "candidate reference body\n", encoding="utf-8",
    )
    # These two MUST be refused by the runner:
    (override_dir / "eval.yaml").write_text(
        "judge_model: HACKED\n", encoding="utf-8",
    )
    (override_dir / "evals").mkdir()
    (override_dir / "evals" / "case" / "scenario.yaml").parent.mkdir(parents=True, exist_ok=True)
    (override_dir / "evals" / "case" / "scenario.yaml").write_text(
        "query: HACKED\n", encoding="utf-8",
    )

    captured: dict = {}

    def fake_run(**kwargs):
        cwd = kwargs["cwd"]
        # Confirm the override landed in the sandbox by reading SKILL.md
        skill_md = Path(cwd) / "skills" / "demo" / "SKILL.md"
        captured["skill_md_body"] = skill_md.read_text(encoding="utf-8")
        captured["ref_body"] = (
            Path(cwd) / "skills" / "demo" / "references" / "guide.md"
        ).read_text(encoding="utf-8")
        # eval.yaml in the sandbox must still be the BASELINE version
        # (the one that came from the git archive), NOT the override.
        captured["eval_yaml_body"] = (
            Path(cwd) / "skills" / "demo" / "eval.yaml"
        ).read_text(encoding="utf-8")

        target = Path(cwd) / "features" / "foo" / "production" / "out.md"
        target.write_text("override produced this", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=5,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="ok",
            tool_calls=[{"name": "Write", "input": {"file_path": str(target)}}],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    outcome = R.run(
        repo_root=root, target="demo/case", skill_override=override_dir,
    )
    assert outcome.overall == "PASS"

    # (a) sandbox contains the override SKILL.md + references file
    assert "DEMO CANDIDATE" in captured["skill_md_body"]
    assert "candidate reference body" in captured["ref_body"]
    # (b) sandbox eval.yaml is the BASELINE (HACKED line was rejected)
    assert "HACKED" not in captured["eval_yaml_body"]
    assert "judge_model: m" in captured["eval_yaml_body"]

    # (c) run.json carries skill_override per §10.5 schema
    run_json = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    so = run_json["skill_override"]
    assert so["dir"] == str(override_dir)
    assert "sha256_per_file" in so
    assert "SKILL.md" in so["sha256_per_file"]
    assert "references/guide.md" in so["sha256_per_file"]
    # eval.yaml + evals/ were skipped — they MUST NOT appear in sha map
    assert "eval.yaml" not in so["sha256_per_file"]
    assert not any(k.startswith("evals/") for k in so["sha256_per_file"])
    # sha values look like sha256 hex
    for sha in so["sha256_per_file"].values():
        assert len(sha) == 64
        int(sha, 16)  # valid hex


def test_skill_override_run_cannot_be_snapshotted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stage 2.6 + 2.1 integration: snapshot CLI refuses override runs."""
    root = _init_repo(tmp_path)
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    override_dir = tmp_path / "candidate"
    override_dir.mkdir()
    (override_dir / "SKILL.md").write_text("# CANDIDATE", encoding="utf-8")

    def fake_run(**kw):
        (Path(kw["cwd"]) / "features/foo/production/out.md").write_text(
            "ok", encoding="utf-8",
        )
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kw["model"], actual_model=kw["model"],
            final_text="", tool_calls=[],
            stream_path=str(kw["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    outcome = R.run(
        repo_root=root, target="demo/case", skill_override=override_dir,
    )
    assert outcome.overall == "PASS"

    # Now try to snapshot this PASS run — must be refused (§10.5).
    from one_context.eval.baseline import snapshot, SnapshotError
    scn_dir = root / "skills" / "demo" / "evals" / "case"
    with pytest.raises(SnapshotError, match="--skill-override run"):
        snapshot(scenario_dir=scn_dir, reason="should fail")
    # baseline dir must not exist
    assert not (scn_dir / "__baselines").exists()


def test_target_path_sha256_stable_across_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same fixture tree → same target_path_sha256 across two runs."""
    root = _init_repo(tmp_path)
    sb_root = tmp_path / "sb"; sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        # do NOT modify the target subtree so sha stays computable
        # from the prepared sandbox state alone
        Path(kwargs["stream_path"]).write_text("{}\n", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"], actual_model=kwargs["model"],
            final_text="noop",
            tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    # prune_on_pass=False: PASS-rolling would delete out1's runId before
    # we read out1.run_json_path on the next line.
    out1 = R.run(repo_root=root, target="demo/case", prune_on_pass=False)
    out2 = R.run(repo_root=root, target="demo/case", prune_on_pass=False)
    j1 = json.loads(out1.run_json_path.read_text(encoding="utf-8"))
    j2 = json.loads(out2.run_json_path.read_text(encoding="utf-8"))
    assert j1["target_path_sha256"] == j2["target_path_sha256"]
    assert len(j1["target_path_sha256"]) == 64


def test_runner_writes_scenario_inputs_and_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 2.5.1 end-to-end: run.json has scenario_inputs + events;
    __reports/<run_id>/inputs/ has overlay + ground_truth copies."""
    root = _init_repo(tmp_path, with_overlay_patch=True)

    # add a ground_truth file so we can also assert the gt copy
    gt_dir = root / "skills/demo/evals/case/ground_truth"
    gt_dir.mkdir(parents=True, exist_ok=True)
    (gt_dir / "pass-01-happy.yaml").write_text(
        "expected: pass\nfinal_text: ok\nartifacts: []\n", encoding="utf-8")
    (gt_dir / "fail-01-empty.yaml").write_text(
        "expected: fail\nfinal_text: ''\nartifacts: []\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "+gt"], cwd=str(root), check=True)

    sb_root = tmp_path / "sb"; sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        cwd = kwargs["cwd"]
        # ISS-020: cwd is sandbox root; skill writes under target_path/
        target = Path(cwd) / "features" / "foo" / "production" / "out.md"
        target.write_text("body — written by mock skill", encoding="utf-8")
        # Write a realistic 3-event stream-json so events parser has data.
        stream_path = Path(kwargs["stream_path"])
        stream_path.write_text(
            '{"type":"system","subtype":"init","model":"m","cwd":"/x","tools":["Read","Write"]}\n'
            '{"type":"assistant","message":{"content":['
              '{"type":"thinking","thinking":"I should write out.md."},'
              '{"type":"tool_use","id":"tu1","name":"Write",'
                '"input":{"file_path":"/x/out.md","content":"hello"}}'
            ']}}\n'
            '{"type":"user","message":{"content":['
              '{"type":"tool_result","tool_use_id":"tu1","content":"ok"}'
            ']}}\n'
            '{"type":"result","total_cost_usd":0.001,"result":"done"}\n',
            encoding="utf-8",
        )
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=10,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="done",
            tool_calls=[{"name": "Write", "input": {"file_path": str(target)}}],
            stream_path=str(stream_path),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"
    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))

    # ── scenario_inputs block ──
    assert "scenario_inputs" in run
    si = run["scenario_inputs"]
    # raw template is kept; rendered version available alongside
    assert "{{ target_path }}" in si["query"]
    assert "{{ target_path }}" not in si["query_rendered"]
    assert si["target_path"] == "features/foo/"
    assert "production/out.md" in si["rubric_default"]
    # Stage 2.X.4+: si.provider.model is the *effective* model (post resolution),
    # while si.provider.model_yaml is the raw scenario.yaml value. Fixture writes
    # `model: m`; assert via the raw-yaml channel since the conftest autouse stub
    # routes effective_model through a synthetic settings.json.
    assert si["provider"]["model_yaml"] == "m"
    assert si["provider"]["timeoutMs"] == 1000

    # overlay_files metadata: one entry per overlay.apply src
    overlay_files = si["overlay_files"]
    assert len(overlay_files) == 1
    of = overlay_files[0]
    assert of["src"] == "./patch-spec.md"
    assert "{{ target_path }}" in of["dst"] or of["dst"].endswith("spec.md")
    assert of["size"] > 0

    # ground_truth_files metadata
    gt_files = {f["name"]: f for f in si["ground_truth_files"]}
    assert "pass-01-happy" in gt_files
    assert gt_files["pass-01-happy"]["expected"] == "pass"
    assert gt_files["fail-01-empty"]["expected"] == "fail"

    # ── overlay_applied surfaced at the run.json top level ──
    assert "overlay_applied" in run
    assert len(run["overlay_applied"]) == 1
    oa = run["overlay_applied"][0]
    # Path("./patch-spec.md") normalises to "patch-spec.md" when stringified
    assert oa["src"] == "patch-spec.md"
    # dst is sandbox-relative; target_path interpolated
    assert oa["dst"] == "features/foo/spec.md"
    assert len(oa["sha256"]) == 64

    # ── events block ──
    assert "events" in run
    events = run["events"]
    kinds = [e["kind"] for e in events]
    assert kinds == ["sys.init", "think", "tool_use", "tool_result", "result"]
    # Write.content was stripped to placeholder, not the literal "hello"
    write_ev = next(e for e in events if e["kind"] == "tool_use")
    assert "see artifact" in write_ev["input"]["content"]
    assert write_ev["input"]["file_path"] == "/x/out.md"

    # ── inputs/ directory physically copied ──
    inputs_dir = outcome.report_dir / "inputs"
    assert (inputs_dir / "overlay" / "patch-spec.md").is_file()
    assert (inputs_dir / "ground_truth" / "pass-01-happy.yaml").is_file()
    assert (inputs_dir / "ground_truth" / "fail-01-empty.yaml").is_file()


def test_list_and_clean(tmp_path: Path) -> None:
    root = _init_repo(tmp_path)
    rows = R.list_scenarios(root)
    assert ("demo", "case") in rows

    # create a fake reports dir to clean
    rd = root / "skills" / "demo" / "evals" / "case" / "__reports" / "abc"
    rd.mkdir(parents=True)
    (rd / "x").write_text("y", encoding="utf-8")
    n = R.clean_reports(root)
    assert n == 1
    assert not (root / "skills" / "demo" / "evals" / "case" / "__reports").exists()


# ── Stage 2.X.4: model resolution via settings.json ───────────────────────


@pytest.mark.real_model_profiles
def test_runner_resolves_model_from_settings_when_yaml_omits_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scenario.yaml without `provider.model` → runner reads settings.json env.ANTHROPIC_MODEL.

    Verifies (a) provider gets the resolved model, (b) run.json records
    model_source="settings" + model_yaml=None.

    Stage 2.X.6 note: `model_profiles.resolve_settings_path` now picks the
    settings.json from a fixed enum, so we monkeypatch it directly to point
    at this test's fake settings file (the `@real_model_profiles` mark
    opts out of conftest's autouse stub).
    """
    root = _init_repo(tmp_path)
    # Overwrite scenario.yaml to drop provider.model — keep everything else minimal.
    scn = root / "skills" / "demo" / "evals" / "case"
    (scn / "scenario.yaml").write_text(
        "query: |\n"
        "  please write under {{ target_path }}\n"
        "target_path: features/foo/\n"
        "provider:\n"
        "  timeoutMs: 1000\n"
        "threshold: 0.5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "drop provider.model"], cwd=str(root), check=True)

    # Build a fake settings.json with ANTHROPIC_MODEL=Kimi-K2.6, then route
    # model_profiles to it so runner's settings_resolver reads our value.
    settings_path = tmp_path / "fake-settings.json"
    settings_path.write_text(
        json.dumps({"env": {"ANTHROPIC_MODEL": "Kimi-K2.6"}}),
        encoding="utf-8",
    )
    from one_context.eval import model_profiles
    monkeypatch.setattr(
        model_profiles, "resolve_settings_path",
        lambda model_name: str(settings_path),
    )
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)

    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    captured_model: dict[str, str] = {}

    def fake_run(**kwargs):
        captured_model["model"] = kwargs["model"]
        target = Path(kwargs["cwd"]) / "features" / "foo" / "production" / "out.md"
        target.write_text("ok", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="done", tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"
    # (a) provider received the settings-resolved model.
    assert captured_model["model"] == "Kimi-K2.6"
    # (b) run.json records source provenance.
    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    prov = run["scenario_inputs"]["provider"]
    assert prov["model"] == "Kimi-K2.6"
    assert prov["model_source"] == "settings"
    assert prov["model_yaml"] is None


def test_runner_env_override_wins_over_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """$ONECXT_MODEL_OVERRIDE takes precedence even when scenario.yaml sets model."""
    root = _init_repo(tmp_path)  # this scenario has provider.model = "m"

    monkeypatch.setenv("ONECXT_MODEL_OVERRIDE", "GLM-5.1")
    monkeypatch.setenv("ONECXT_CLAUDE_SETTINGS_DISABLE_DEFAULT", "1")
    monkeypatch.delenv("ONECXT_CLAUDE_SETTINGS", raising=False)

    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    seen: dict[str, str] = {}

    def fake_run(**kwargs):
        seen["model"] = kwargs["model"]
        target = Path(kwargs["cwd"]) / "features" / "foo" / "production" / "out.md"
        target.write_text("ok", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"], actual_model=kwargs["model"],
            final_text="done", tool_calls=[],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"
    assert seen["model"] == "GLM-5.1"
    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))
    assert run["scenario_inputs"]["provider"]["model_source"] == "env_override"
    assert run["scenario_inputs"]["provider"]["model_yaml"] == "m"  # yaml still recorded as-was


@pytest.mark.real_model_profiles
def test_runner_raises_when_no_model_source_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """yaml omits model + settings has no ANTHROPIC_MODEL + no env override → clear error.

    Stage 2.X.6 note: model_profiles owns the settings.json path now, so
    we feed it a settings file that exists but lacks `env.ANTHROPIC_MODEL`
    to exercise the settings_resolver fallback failure.
    """
    root = _init_repo(tmp_path)
    scn = root / "skills" / "demo" / "evals" / "case"
    (scn / "scenario.yaml").write_text(
        "query: q\ntarget_path: features/foo/\nprovider:\n  timeoutMs: 1000\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=str(root), check=True)

    # Settings file exists but carries no ANTHROPIC_MODEL → settings_resolver
    # has nothing to fall back to → ModelResolveError → runner re-wraps as
    # "cannot resolve provider model".
    empty_settings = tmp_path / "empty-settings.json"
    empty_settings.write_text(json.dumps({"env": {}}), encoding="utf-8")
    from one_context.eval import model_profiles
    monkeypatch.setattr(
        model_profiles, "resolve_settings_path",
        lambda model_name: str(empty_settings),
    )
    monkeypatch.delenv("ONECXT_MODEL_OVERRIDE", raising=False)
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(tmp_path / "sb"))
    (tmp_path / "sb").mkdir()

    with pytest.raises(RuntimeError, match="cannot resolve provider model"):
        R.run(repo_root=root, target="demo/case")


def test_runner_overlay_dst_handles_symlinked_tmp_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression: on macOS the system /tmp is a symlink to /private/tmp.
    `fixture.apply_overlay` resolves sandbox_root so OverlayApplied.dst
    starts with the resolved prefix, while `sandbox.path` keeps the
    unresolved one. `runner.py` MUST resolve sandbox.path before computing
    `relative_to`, otherwise every macOS run that uses overlay.apply blows
    up with "is not in the subpath of".

    We reproduce by pointing ONECXT_EVAL_TMP_ROOT at a symlink whose
    target is a different real path.
    """
    root = _init_repo(tmp_path, with_overlay_patch=True)

    # Build an unresolved alias: tmp_path/sb-link → tmp_path/sb-real.
    real_sb = tmp_path / "sb-real"
    real_sb.mkdir()
    alias_sb = tmp_path / "sb-link"
    alias_sb.symlink_to(real_sb)

    # _tmp_root() returns Path(env) without resolving — sandbox.path stays
    # under sb-link/ while fixture.apply_overlay resolves to sb-real/.
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(alias_sb))

    def fake_run(**kwargs):
        cwd = kwargs["cwd"]
        target = Path(cwd) / "features" / "foo" / "production" / "out.md"
        target.write_text("body", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=10,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="done",
            tool_calls=[{"name": "Write", "input": {"file_path": str(target)}}],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: '{"pass": true, "score": 0.9, "reason": "ok"}',
    )

    # Before the fix this raised ValueError("... is not in the subpath of ...").
    outcome = R.run(repo_root=root, target="demo/case")
    run = json.loads(outcome.run_json_path.read_text(encoding="utf-8"))

    assert len(run["overlay_applied"]) == 1
    assert run["overlay_applied"][0]["dst"] == "features/foo/spec.md"
    assert run["overlay_added"] == ["features/foo/spec.md"]


# ── Phase 2.6.A: __reports/ rolling on PASS ─────────────────────────────────


def _setup_pass_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    judge_pass: bool = True,
) -> Path:
    """Wire up a working sandbox + mocked provider + replay judge that
    can be flipped between PASS and FAIL via `judge_pass`. Returns the
    repo root.
    """
    root = _init_repo(tmp_path)
    sb_root = tmp_path / "sb"
    sb_root.mkdir()
    monkeypatch.setenv("ONECXT_EVAL_TMP_ROOT", str(sb_root))

    def fake_run(**kwargs):
        target = Path(kwargs["cwd"]) / "features" / "foo" / "production" / "out.md"
        target.write_text("body", encoding="utf-8")
        return prov_mod.ProviderResult(
            ok=True, exit_code=0, duration_ms=1,
            requested_model=kwargs["model"],
            actual_model=kwargs["model"],
            final_text="done",
            tool_calls=[{"name": "Write", "input": {"file_path": str(target)}}],
            stream_path=str(kwargs["stream_path"]),
            timeout=False, stderr_tail="", raw={},
        )
    monkeypatch.setattr(prov_mod, "run_provider", fake_run)

    judge_payload = (
        '{"pass": true, "score": 0.9, "reason": "ok"}'
        if judge_pass
        else '{"pass": false, "score": 0.1, "reason": "no"}'
    )
    monkeypatch.setattr(
        J, "_spawn_judge",
        lambda prompt, model: judge_payload,
    )
    return root


def test_pass_prunes_old_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PASS run keeps its own runId; older runIds + index.html are removed."""
    root = _setup_pass_run(tmp_path, monkeypatch, judge_pass=True)
    scn_dir = root / "skills" / "demo" / "evals" / "case"
    reports = scn_dir / "__reports"

    # Plant an ancient FAIL-shaped runId from the year 2001 (unix 1000000000)
    # so it is unambiguously "older" than any real run we trigger now.
    ancient = reports / "1000000000-deadbe"
    ancient.mkdir(parents=True)
    (ancient / "run.json").write_text("{}", encoding="utf-8")
    # A bogus index.html — should be deleted on PASS.
    (reports / "index.html").write_text("<html></html>", encoding="utf-8")

    # Plant a fake __baselines/ alongside __reports/ — must NOT be touched.
    baseline_dir = scn_dir / "__baselines"
    baseline_dir.mkdir()
    (baseline_dir / "baseline.json").write_text('{"pin":1}', encoding="utf-8")

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"

    surviving = sorted(p.name for p in reports.iterdir() if p.is_dir())
    assert surviving == [outcome.run_id], (
        f"expected only {outcome.run_id}, got {surviving}"
    )
    assert not ancient.exists()
    assert not (reports / "index.html").exists()
    # __baselines/ untouched
    assert (baseline_dir / "baseline.json").read_text(encoding="utf-8") == '{"pin":1}'


def test_fail_does_not_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FAIL runs accumulate. Older runIds are kept until the next PASS."""
    root = _setup_pass_run(tmp_path, monkeypatch, judge_pass=False)
    scn_dir = root / "skills" / "demo" / "evals" / "case"
    reports = scn_dir / "__reports"

    out1 = R.run(repo_root=root, target="demo/case")
    out2 = R.run(repo_root=root, target="demo/case")
    assert out1.overall == "FAIL"
    assert out2.overall == "FAIL"

    surviving = {p.name for p in reports.iterdir() if p.is_dir()}
    assert out1.run_id in surviving
    assert out2.run_id in surviving


def test_repeat_aggregate_pass_prunes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """repeat=3 with single-run results PASS/PASS/FAIL → aggregate PASS
    (pass_rate=2/3 ≥ 2/3); ancient runId is pruned. Locks in the
    decision that prune lives at run() (post-aggregate), not _single_run.
    """
    root = _setup_pass_run(tmp_path, monkeypatch, judge_pass=True)
    scn_dir = root / "skills" / "demo" / "evals" / "case"
    # Switch the scenario to repeat=3 so run() walks the aggregate branch.
    (scn_dir / "scenario.yaml").write_text(
        "query: |\n"
        "  please write under {{ target_path }}\n"
        "target_path: features/foo/\n"
        "provider:\n"
        "  model: m\n"
        "  timeoutMs: 1000\n"
        "threshold: 0.5\n"
        "repeat: 3\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True)
    subprocess.run(["git", "commit", "-q", "-m", "+repeat"], cwd=str(root), check=True)

    reports = scn_dir / "__reports"
    reports.mkdir(parents=True, exist_ok=True)
    ancient = reports / "1000000000-deadbe"
    ancient.mkdir()
    (ancient / "run.json").write_text("{}", encoding="utf-8")

    outcome = R.run(repo_root=root, target="demo/case")
    assert outcome.overall == "PASS"

    # Only the last run's runId survives (the one whose run.json gets
    # rewritten with the aggregated overall) — earlier _single_run iters
    # write to other runIds, so they are also strictly older than the
    # final one and get pruned together.
    surviving = sorted(p.name for p in reports.iterdir() if p.is_dir())
    assert surviving == [outcome.run_id]
    assert not ancient.exists()


def test_skill_override_pass_skips_prune(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A PASS run launched via --skill-override must NOT prune real history.

    Override runs are debug artifacts (baseline.snapshot rejects them);
    they would otherwise let a candidate skill quietly delete real
    baseline data.
    """
    root = _setup_pass_run(tmp_path, monkeypatch, judge_pass=True)
    scn_dir = root / "skills" / "demo" / "evals" / "case"
    reports = scn_dir / "__reports"

    # First, a normal PASS — leaves runId A.
    out_real = R.run(repo_root=root, target="demo/case")
    assert out_real.overall == "PASS"

    # Now an override candidate: same skill body but routed through the
    # --skill-override codepath so run.json carries `skill_override`.
    override_dir = tmp_path / "candidate"
    override_dir.mkdir()
    (override_dir / "SKILL.md").write_text("# CANDIDATE", encoding="utf-8")

    out_override = R.run(
        repo_root=root, target="demo/case", skill_override=override_dir,
    )
    assert out_override.overall == "PASS"

    surviving = {p.name for p in reports.iterdir() if p.is_dir()}
    assert out_real.run_id in surviving, "override run must not delete real history"
    assert out_override.run_id in surviving


def test_prune_helper_skips_unparseable_runid(tmp_path: Path) -> None:
    """The helper is defensive: anything whose name doesn't parse as
    `<int>-<rest>` is left alone (forward-compat for runId rename).
    """
    scn_dir = tmp_path / "scn"
    reports = scn_dir / "__reports"
    reports.mkdir(parents=True)

    keep_id = "2000000000-keepme"
    keep_dir = reports / keep_id
    keep_dir.mkdir()
    (keep_dir / "run.json").write_text("{}", encoding="utf-8")

    older = reports / "1000000000-old123"
    older.mkdir()
    (older / "run.json").write_text("{}", encoding="utf-8")

    weird = reports / "weird-name-no-prefix"
    weird.mkdir()
    (weird / "run.json").write_text("{}", encoding="utf-8")

    (reports / "index.html").write_text("<html></html>", encoding="utf-8")

    n = R._prune_reports_after_pass(scn_dir, keep_run_id=keep_id)

    assert n == 2  # older dir + index.html
    assert keep_dir.is_dir()
    assert not older.exists()
    assert weird.is_dir(), "unparseable name must be preserved"
    assert not (reports / "index.html").exists()
