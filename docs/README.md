# Documentation index

Tool-neutral documentation for the one-context umbrella repository.

| Document | Purpose |
|----------|---------|
| [architecture.md](architecture.md) | Layer model: registry, repos, knowledge, features, adapters, CLI |
| [manifests.md](manifests.md) | Reference for `meta/repos.yaml`, `workspaces.yaml`, `profiles.yaml` |
| [using-agents.md](using-agents.md) | How agents are defined in `meta/agents.yaml`, `onecxt adapt`, and multi-agent workflow |
| [MEMORY.md](MEMORY.md) | Optional placeholder for local notes (not used by core tooling) |
| [ai-infra/README.md](ai-infra/README.md) | Optional extension point for infra notes |
| [templates/README.md](templates/README.md) | Example personal agent template filenames (not committed as live config) |
| [templates/deploy.yaml](templates/deploy.yaml) | Example `deploy.yaml` for SRE flows |
| [diagrams/](diagrams/) | Self-contained HTML diagrams (optional; not used by CLI) |
| [images/](images/) | PNG/JPEG assets referenced from the repository root `README.md` (optional branding) |

After changing `meta/` or workspace knowledge paths, run `onecxt doctor` and `onecxt adapt --all` as needed.
