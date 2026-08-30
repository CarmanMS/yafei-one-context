# one-context CLI

`one-context` is the Python package behind the `onecxt` CLI in
[`CarmanMS/yafei-one-context`](https://github.com/CarmanMS/yafei-one-context).
This fork is a research-oriented multi-repository context control plane, with
mathematical research as its current focus.

## Install

From the repository root containing `meta/repos.yaml`:

```bash
python -m pip install -e ./packages/one-context
```

For development (tests), use:

```bash
python -m pip install -e "./packages/one-context[dev]"
```

## Run

The module entry point works on Windows, macOS, and Linux:

```bash
python -m one_context --help
```

After installation, the same commands are available through `onecxt`.

Use `ONECXT_ROOT` or `--root PATH` when your shell is not inside the workspace tree.

## Common commands

```bash
onecxt doctor
onecxt repo list
onecxt workspace list
onecxt workspace show WORKSPACE_ID
onecxt context export WORKSPACE_ID
onecxt context export WORKSPACE_ID --format markdown
onecxt context export WORKSPACE_ID --format markdown --compress --target-tokens 8000
onecxt profile list
onecxt agent list
onecxt skills list
onecxt sync
onecxt sync your-repo-id
onecxt adapt WORKSPACE_ID
onecxt adapt WORKSPACE_ID --only hermes --dry-run
```

Personal Obsidian vault content is not read directly by this package. Vault
workflows use the repository's Obsidian skill and Local REST API boundary.

## Test

```bash
python -m pytest packages/one-context/tests
```

## License

MIT. See the [package license](https://github.com/CarmanMS/yafei-one-context/blob/main/packages/one-context/LICENSE).
