# SBE automation (Tum-Soil-Biophysics/.github)

Central automation for the GitHub organization of the Professorship for Soil Biophysics and Environmental Systems (TUM).

## What happens automatically

1. A member creates a repository from [project-template](https://github.com/Tum-Soil-Biophysics/project-template) (private), uploads the code and fills in `.zenodo.json`.
2. At acceptance of the article, Prof. Zare makes the repository **public** and publishes a **release** (e.g. `v1.0.0`).
3. The release is archived on Zenodo: new DOI, placed in the community [TUM Soil Biophysics](https://zenodo.org/communities/tum-sbe). The DOI is added to the release notes. Later releases become new versions of the same record.

Private repositories and pre-releases are never published.

## Files

| File | Purpose |
|---|---|
| `.github/workflows/zenodo-release.yml` | The release-to-Zenodo logic, called by every repository |
| `scripts/zenodo_release.py` | Checks `.zenodo.json` and talks to Zenodo |
| `workflow-templates/` | The short file each repository needs (also under *Actions > New workflow*) |
| `.github/workflows/audit.yml` | Weekly check that every public repository is connected; opens an issue if not |
| `audit-exceptions.txt` | Repositories the audit skips (e.g. code that already has its own Zenodo DOI) |

## Connect a repository that was not made from the template

In the repository: *Actions > New workflow > "Zenodo DOI on release (SBE)" > Commit*, then add a filled `.zenodo.json` (copy it from the template).

## Check before releasing

*Actions > Zenodo DOI on release > Run workflow*, enter the tag, keep **dry run** ticked. The run reports whether `.zenodo.json` is valid and whether a new record or a new version would be created. Nothing is published.

## Requirements (already set)

- Organization secret `ZENODO_TOKEN` (Zenodo token of the group account), visible to public repositories.
- Optional variable `ZENODO_SANDBOX=true` in a repository to test on sandbox.zenodo.org (needs a sandbox token).
