# Releasing pcp-pmda-unifi

## How Versioning Works

There is **no version string in the code**. The git tag is the single source of truth.

[hatch-vcs](https://github.com/ofek/hatch-vcs) reads the most recent `v`-prefixed git tag
and injects it into the build. If you're on tag `v0.3.0`, the package version is `0.3.0`.
Between tags, dev builds get versions like `0.3.dev12` (12 commits since the last tag).

## Release Checklist

1. **Make sure `main` is clean and CI is green.**

2. **Create a GitHub Release** (which creates the git tag for you):
   - Go to GitHub → Releases → "Draft a new release"
   - Click "Choose a tag" and **type the new tag** (e.g., `v0.3.0`) — GitHub will create it
   - Target: `main`
   - Title: `v0.3.0` (or whatever you're shipping)
   - Write release notes (GitHub can auto-generate these from PRs)
   - Hit **Publish release**

3. **That's it.** The release workflow handles the rest:
   - Validates the tag matches the built version (catches typos)
   - Publishes to PyPI
   - Builds RPM and DEB and attaches them to the GitHub Release

## Gotchas

### Tag format matters
Tags **must** be `v` prefixed: `v0.3.0`, not `0.3.0`. The workflow strips the `v` when
comparing against the package version.

### Tags must be on the right commit
If you create a tag on a branch that hasn't been merged to `main`, the release will
build whatever is on that commit. Always tag from `main` (the GitHub Release UI handles
this if you set "Target: main").

### PyPI releases are permanent
You cannot overwrite a version on PyPI. If `v0.3.0` goes out broken, you must fix and
release `v0.3.1`. There is no undo.

### PyPI Trusted Publisher must be configured
Before your first release, set up the OIDC trust on pypi.org:
- Package settings → Publishing → Add publisher
- Owner: your GitHub org/user
- Repository: `pmunfi`
- Workflow: `release.yml`
- Environment: `pypi`

And on GitHub: Settings → Environments → create `pypi`.

### RPM and DEB builds use `continue-on-error`
These are best-effort. If they fail, the PyPI publish still succeeds. Check the
workflow run if RPM/DEB artifacts are missing from the release.

### Local dev version looks weird
Running `python -c "import pcp_pmda_unifi; print(pcp_pmda_unifi.__version__)"` in a dev
checkout will show something like `0.3.dev12` or `0.0.0+unknown` (if not installed).
This is normal. The clean version only appears in tagged builds.

## Semver Cheat Sheet

- **Patch** (`0.3.0` → `0.3.1`): bug fixes, no new features
- **Minor** (`0.3.1` → `0.4.0`): new features, backwards compatible
- **Major** (`0.4.0` → `1.0.0`): breaking changes

Until `1.0.0`, all bets are off anyway.
