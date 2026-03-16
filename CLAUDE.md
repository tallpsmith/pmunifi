# pmunfi Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-15

## Active Technologies
- In-memory snapshot cache (copy-on-write), `pmdaCache` persistent instance ID mapping on disk (001-unifi-pmda)

- Python 3.8+ (must support RHEL 9 / Ubuntu 20.04 LTS system Python) + `requests` (pip), `pcp.pmda` + `cpmda` (system package) (001-unifi-pmda)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.8+ (must support RHEL 9 / Ubuntu 20.04 LTS system Python): Follow standard conventions

## Recent Changes
- 001-unifi-pmda: Added Python 3.8+ (must support RHEL 9 / Ubuntu 20.04 LTS system Python) + `requests` (pip), `pcp.pmda` + `cpmda` (system package)

- 001-unifi-pmda: Added Python 3.8+ (must support RHEL 9 / Ubuntu 20.04 LTS system Python) + `requests` (pip), `pcp.pmda` + `cpmda` (system package)

<!-- MANUAL ADDITIONS START -->

## CI Monitoring

After every `git push` (to any branch or PR), launch a background agent to monitor
the GitHub Actions CI run. The agent should:

1. Use `gh run list --branch <branch> --limit 1` to find the triggered run
2. Poll with `gh run watch <run-id> --exit-status` (or periodic `gh run view`) until completion
3. If the run **fails**, immediately notify with the failing job name(s) and relevant log output (`gh run view --log-failed`)
4. If the run **passes**, confirm briefly

This ensures build failures are caught and addressed without the user having to
manually check GitHub Actions.

<!-- MANUAL ADDITIONS END -->
