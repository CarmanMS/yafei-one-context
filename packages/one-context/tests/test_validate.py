"""Tests for one_context.validate — doctor() cross-checks."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from one_context.validate import (
    DoctorResult,
    doctor,
    _collect_all_knowledge_references,
    _expand_directory_refs,
    _check_at_references,
    generate_knowledge_graph,
    AT_REF_PATTERN,
)


class TestDoctor:
    def test_clean_state(self, tmp_root_with_workspaces: Path):
        # Create repo dirs with .git so doctor sees them
        for name in ("alpha", "beta"):
            d = tmp_root_with_workspaces / "repos" / ("develop" if name == "alpha" else "research") / name
            d.mkdir(parents=True, exist_ok=True)
            (d / ".git").mkdir()
        result = doctor(tmp_root_with_workspaces)
        assert result.errors == []
        assert result.warnings == []

    def test_missing_repo_dir_warning(self, tmp_root_with_workspaces: Path):
        result = doctor(tmp_root_with_workspaces)
        assert any("local path missing" in w for w in result.warnings)

    def test_not_git_repo_warning(self, tmp_root_with_workspaces: Path):
        d = tmp_root_with_workspaces / "repos" / "develop" / "alpha"
        d.mkdir(parents=True)
        # no .git directory
        result = doctor(tmp_root_with_workspaces)
        assert any("not a git repo" in w for w in result.warnings)

    def test_unknown_repo_in_workspace(self, tmp_root: Path):
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: ws1
                    repos:
                      - nonexistent-repo
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("unknown repo id" in e for e in result.errors)

    def test_unknown_profile_in_workspace(self, tmp_root: Path):
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: ws1
                    repos:
                      - alpha
                    profiles:
                      - nonexistent-profile
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("unknown profile id" in e for e in result.errors)

    def test_bad_repos_yaml_returns_error(self, tmp_path: Path):
        meta = tmp_path / "meta"
        meta.mkdir()
        (meta / "repos.yaml").write_text("not valid", encoding="utf-8")
        result = doctor(tmp_path)
        assert len(result.errors) > 0

    def test_bad_workspaces_yaml_error(self, tmp_root: Path):
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            "- just a list\n", encoding="utf-8"
        )
        result = doctor(tmp_root)
        assert any("mapping" in e for e in result.errors)

    def test_bad_profiles_yaml_error(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            "- just a list\n", encoding="utf-8"
        )
        result = doctor(tmp_root)
        assert any("mapping" in e for e in result.errors)

    def test_workspace_repos_not_list(self, tmp_root: Path):
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: ws1
                    repos: "not-a-list"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("'repos' must be a list" in e for e in result.errors)

    def test_workspace_profiles_not_list(self, tmp_root: Path):
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: ws1
                    repos:
                      - alpha
                    profiles: "not-a-list"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("'profiles' must be a list" in e for e in result.errors)


class TestDoctorInheritance:
    """Doctor checks for extends / mixins validation."""

    def test_extends_unknown_profile(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                profiles:
                  - id: child
                    name: Child
                    extends: nonexistent
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("extends unknown profile" in e for e in result.errors)

    def test_multi_layer_extends(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                profiles:
                  - id: grandparent
                    name: GP
                  - id: parent
                    name: Parent
                    extends: grandparent
                  - id: child
                    name: Child
                    extends: parent
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("multi-layer inheritance" in e for e in result.errors)

    def test_parent_with_mixins(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                mixins:
                  - id: mx
                    name: MX
                profiles:
                  - id: parent
                    name: Parent
                    mixins:
                      - mx
                  - id: child
                    name: Child
                    extends: parent
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("must not have 'mixins'" in e for e in result.errors)

    def test_unknown_mixin_reference(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                profiles:
                  - id: p1
                    name: P1
                    mixins:
                      - nonexistent
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("unknown mixin" in e for e in result.errors)

    def test_mixin_with_extends_is_error(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                mixins:
                  - id: bad-mixin
                    name: Bad
                    extends: something
                profiles:
                  - id: p1
                    name: P1
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("mixins must not have 'extends'" in e for e in result.errors)

    def test_mixin_with_mixins_is_error(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                mixins:
                  - id: bad-mixin
                    name: Bad
                    mixins:
                      - something
                profiles:
                  - id: p1
                    name: P1
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("mixins must not have 'mixins'" in e for e in result.errors)

    def test_valid_inheritance_no_errors(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                mixins:
                  - id: strict
                    name: Strict
                    behavior:
                      safety_level: conservative
                profiles:
                  - id: base
                    name: Base
                    behavior:
                      plan_first: false
                  - id: child
                    name: Child
                    extends: base
                    mixins:
                      - strict
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert result.errors == []


class TestDoctorAgents:
    """Doctor checks for agents.yaml validation."""

    def test_agent_missing_role(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: bad-agent
                    name: Bad
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("missing required 'role'" in e for e in result.errors)

    def test_agent_invalid_role(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: bad-agent
                    name: Bad
                    role: nonexistent-role
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("invalid role" in e for e in result.errors)

    def test_agent_unknown_profile_reference(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: bad-agent
                    name: Bad
                    role: dev
                    profile: nonexistent-profile
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("unknown profile" in e for e in result.errors)

    def test_agent_missing_knowledge_path_warning(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: test-agent
                    name: Test
                    role: dev
                    knowledge:
                      - nonexistent/path/
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("knowledge path not found" in w for w in result.warnings)

    def test_valid_agent_no_errors(self, tmp_root: Path):
        (tmp_root / "meta" / "profiles.yaml").write_text(
            textwrap.dedent("""\
                profiles:
                  - id: default-coding
                    name: Default
            """),
            encoding="utf-8",
        )
        docs_dir = tmp_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "example.md").write_text("example", encoding="utf-8")
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: test-dev
                    name: Dev
                    role: dev
                    profile: default-coding
                    knowledge:
                      - docs/
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert not any("test-dev" in e for e in result.errors)

    def test_worktree_missing_branch_pattern(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: dev
                    name: Dev
                    role: dev
                    worktree:
                      path_pattern: "repos/{repo_id}/.worktrees/{feature_id}"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("branch_pattern" in e for e in result.errors)

    def test_worktree_missing_path_pattern(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: dev
                    name: Dev
                    role: dev
                    worktree:
                      branch_pattern: "feature/{feature_id}"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("path_pattern" in e for e in result.errors)

    def test_worktree_on_non_dev_warns(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: pm
                    name: PM
                    role: pm
                    worktree:
                      branch_pattern: "feature/{feature_id}"
                      path_pattern: "repos/{repo_id}/.worktrees/{feature_id}"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("intended for role=dev" in w for w in result.warnings)

    def test_worktree_placeholder_warnings(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: dev
                    name: Dev
                    role: dev
                    worktree:
                      branch_pattern: "feature/hardcoded"
                      path_pattern: "repos/hardcoded"
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("feature_id" in w for w in result.warnings)
        assert any("repo_id" in w for w in result.warnings)


class TestDoctorKnowledgeIntegrity:
    """Doctor checks repository context without opening the Obsidian vault."""

    def test_workspace_knowledge_path_not_found(self, tmp_root: Path):
        """Workspace referencing a non-existent knowledge path should warn."""
        (tmp_root / "meta" / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: ws1
                    context:
                      knowledge:
                        - docs/nonexistent/
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("knowledge path not found" in w and "ws1" in w for w in result.warnings)

    def test_vault_reference_is_blocked(self, tmp_root: Path):
        (tmp_root / "meta" / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: dev
                    name: Dev
                    role: dev
                    knowledge:
                      - knowledge/private.md
            """),
            encoding="utf-8",
        )
        result = doctor(tmp_root)
        assert any("blocked knowledge path" in error for error in result.errors)

    def test_at_reference_pattern(self):
        """AT_REF_PATTERN should match file refs and exclude email/CSS."""
        text = (
            "See @knowledge/standards/agent-framework.md for details.\n"
            "Also @docs/architecture.md and @features/README.md.\n"
            "Email: user@example.com should NOT match.\n"
            "CSS: @keyframes pulse should NOT match.\n"
        )
        matches = AT_REF_PATTERN.findall(text)
        assert matches == [
            "knowledge/standards/agent-framework.md",
            "docs/architecture.md",
            "features/README.md",
        ]

    def test_dangling_at_reference_warning(self, tmp_root: Path):
        """Dangling @-reference in a .md file should produce a warning."""
        docs_dir = tmp_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "existing.md").write_text("exists", encoding="utf-8")
        # File with a dangling @-reference
        (docs_dir / "broken.md").write_text(
            "See @docs/nonexistent.md for details.\n",
            encoding="utf-8",
        )

        warnings: list[str] = []
        _check_at_references(tmp_root, warnings)
        assert any("dangling" in w and "nonexistent.md" in w for w in warnings)

    def test_valid_at_reference_no_warning(self, tmp_root: Path):
        """Valid @-reference should not produce a warning."""
        docs_dir = tmp_root / "docs"
        docs_dir.mkdir()
        (docs_dir / "target.md").write_text("target content", encoding="utf-8")
        (docs_dir / "source.md").write_text(
            "See @docs/target.md for details.\n",
            encoding="utf-8",
        )

        warnings: list[str] = []
        _check_at_references(tmp_root, warnings)
        assert not any("target.md" in w for w in warnings)

    def test_collect_all_knowledge_references(self):
        """_collect_all_knowledge_references collects from both workspaces and agents."""
        workspaces = [
            {
                "id": "ws1",
                "context": {
                    "knowledge": ["docs/standards/", "docs/architecture.md"],
                },
            }
        ]
        agents = [
            {
                "id": "dev",
                "knowledge": ["features/README.md", "meta/repos.yaml"],
            }
        ]
        refs = _collect_all_knowledge_references(workspaces, agents)
        assert "docs/standards/" in refs
        assert "docs/architecture.md" in refs
        assert "features/README.md" in refs
        assert "meta/repos.yaml" in refs

    def test_expand_directory_refs(self, tmp_root: Path):
        """_expand_directory_refs expands directories to individual .md files."""
        kdir = tmp_root / "docs" / "standards"
        kdir.mkdir(parents=True)
        (kdir / "a.md").write_text("a", encoding="utf-8")
        (kdir / "b.md").write_text("b", encoding="utf-8")
        # Non-markdown file should be excluded
        (kdir / "c.txt").write_text("c", encoding="utf-8")

        refs = {"docs/standards/", "docs/architecture.md"}
        expanded = _expand_directory_refs(tmp_root, refs)
        assert "docs/standards/a.md" in expanded
        assert "docs/standards/b.md" in expanded
        assert "docs/standards/c.txt" not in expanded
        # Non-directory ref passes through unchanged
        assert "docs/architecture.md" in expanded


class TestKnowledgeGraph:
    """Tests for generate_knowledge_graph."""

    def _setup_graph_root(self, tmp_path: Path) -> Path:
        """Create a minimal one-context root with repository context files."""
        meta = tmp_path / "meta"
        meta.mkdir()

        (meta / "repos.yaml").write_text(
            "repos:\n  - url: git@test.local:acme/alpha.git\n    category: develop\n",
            encoding="utf-8",
        )
        (meta / "workspaces.yaml").write_text(
            textwrap.dedent("""\
                workspaces:
                  - id: dev
                    name: Dev
                    context:
                      knowledge:
                        - docs/
            """),
            encoding="utf-8",
        )
        (meta / "agents.yaml").write_text(
            textwrap.dedent("""\
                agents:
                  - id: dev
                    name: Dev
                    role: dev
                    knowledge:
                      - docs/conventions.md
                  - id: pm
                    name: PM
                    role: pm
                    knowledge:
                      - features/add-feature.md
            """),
            encoding="utf-8",
        )

        # Create repository context files
        kdir = tmp_path / "docs"
        kdir.mkdir()
        (kdir / "conventions.md").write_text("# Conventions\n", encoding="utf-8")
        (kdir / "testing.md").write_text("See @docs/conventions.md\n", encoding="utf-8")

        pdir = tmp_path / "features"
        pdir.mkdir()
        (pdir / "add-feature.md").write_text("# Add Feature\n", encoding="utf-8")

        return tmp_path

    def test_graph_contains_mermaid_block(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        assert graph.startswith("```mermaid")
        assert graph.endswith("```")

    def test_graph_contains_agents(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        assert "agent_dev" in graph
        assert "agent_pm" in graph

    def test_graph_contains_knowledge_nodes(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        # conventions.md is referenced by dev agent
        assert "conventions" in graph
        # add-feature.md is referenced by pm agent
        assert "add_feature" in graph or "add-feature" in graph

    def test_graph_contains_edges(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        # Agent → knowledge edges should be present
        assert "reads" in graph

    def test_graph_contains_workspace(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        assert "ws_dev" in graph

    def test_graph_at_ref_edge(self, tmp_path: Path):
        root = self._setup_graph_root(tmp_path)
        graph = generate_knowledge_graph(root)
        # testing.md references conventions.md via @-ref
        assert "@ref" in graph
