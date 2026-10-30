# Fork changes

Upstream baseline: `3cc00a57fa4883050fd5cffeba7adee9d6d0d4d3` on `main`.
Keep changes isolated and merge upstream normally; this file tracks fork-specific
changes rather than replacing the upstream changelog.

## Unreleased work

- Extend the Python version range to include 3.14 and add dbt Core 1.12 and
  Python 3.14 to the CI matrix, retaining the upstream dbt minimum.
- Update the lock and direct development/optional dependencies, including OpenAI,
  pytest, Ruff and setuptools. Remove the Protobuf 5 override: dbt Core 1.12 and
  its current adapters require Protobuf 6.
- Disable Ruff preview lint rules after the Ruff upgrade; formatter preview
  remains enabled. The newer preview rules report existing upstream code and
  should be reviewed separately before they are enabled.
- Refresh the Python lockfile, permit newer `packaging`, and require a fixed
  `virtualenv` in the development extra. Remove the seven-day lock cutoff so
  recent security fixes can be resolved.
- Continue console logging when the log directory is not writable.
- Replace the discontinued `ydata-profiling` distribution with its maintained
  successor `fg-data-profiling` and update imports. The optional workbench can
  generate a profile on Python 3.14.
- Keep the core CLI available on Python 3.10, but require Python 3.11+ for the
  workbench. Workbench dependencies are omitted on Python 3.10 and the CLI
  explains the restriction; Pillow 13 or later is required for the workbench.
- Refresh documentation dependencies, including an explicit `tinypool` 2.x
  override. Docusaurus declares a 1.x range, so this is an intentional compatibility
  override: production build and local development server have been smoke-tested.
- Use SHA-256 for the workbench editor key and correct the Streamlit watcher
  configuration section.
- Find Streamlit beside the current Python executable when it is absent from
  `PATH`, allowing workbench startup from an unactivated virtual environment.
- Adjust integration assertions for dbt 1.12's serialized column fields and
  string-valued unrendered configuration; assert the effective boolean setting.
- Reject unsafe AI-generated staging filenames and paths resolving outside the
  staging directory, serialize descriptions as YAML scalars, and escape source
  names and materialization values as Jinja string literals. See
  `security_best_practices_report.md` for the remaining SQL and filesystem
  trust boundaries.
- Refuse to replace existing generated SQL without `--overwrite`, matching the
  existing YAML policy for model and staging generation.
- Introspect source columns when the manifest has no column documentation, and
  use the source's physical identifier rather than its logical name.
- Fork package version: `1.5.1+liteart.1` (PEP 440 local version).

The upgrade remains in progress until the final dependency, test and security
checks pass. Lockfile updates do not by themselves prove compatibility of all
Python versions, optional extras or adapters.

## Local verification so far

- With Python 3.14.4, dbt Core 1.12.6, DuckDB 1.11.1 and a locally installed
  patched interface: 1009 tests passed, six skipped and branch-aware coverage
  was 75.31%, below the requested 100%. The full run included the updated
  local interface, the Python 3.10 workbench restriction and the subsequent
  source-introspection fix and was repeated after the interface webhook log,
  naming export and lint changes.
- After the source-introspection fix, 22 focused staging and security tests
  passed, including a source whose physical table name differs from its name.
  A separate temporary dbt/DuckDB project confirmed the same introspection
  against a real table; the AI specification was stubbed for this check.
- All optional dependencies were installed and checked in an isolated environment
  with the local interface patch; a later workbench-focused run used IPython 9.
- Both local wheels were also explicitly installed together in a separate fresh
  Python 3.14 environment with the workbench and DuckDB extras. `uv pip check`
  passed, the CLI reported `1.5.1+liteart.1`, dbt Core reported 1.12.6, and
  profiling generated HTML. This still requires providing the interface wheel.
- A fresh Python 3.14.4 environment installed the latest locally built wheels
  with workbench and DuckDB extras and dbt Core 1.12.6. Dependency consistency
  and the CLI version passed; `pip-audit` found no known vulnerabilities in
  published packages but could not audit the two local fork builds via PyPI.
- The earlier local wheels and extras were smoke-tested on Python 3.10.20 with
  dbt Core 1.12.6: dependency consistency, the CLI version and profiling HTML
  passed. However, that workbench environment resolves Pillow 12.3.0, for which
  `pip-audit` reports 39 advisory IDs; the documented fixes require Pillow 13,
  which requires Python 3.11. It is not security-approved for untrusted image
  input. The updated local metadata omits the workbench dependencies on Python
  3.10 and the workbench command refuses to start there. A separate Python
  3.10 installation of the updated wheel with both extras passed `uv pip check`,
  omitted Pillow and Streamlit, refused to start the workbench with the expected
  explanation and produced no known vulnerabilities in its published packages. Both
  local fork builds were skipped by the audit. Neither is a full test matrix.
- Under Python 3.11.15, an installation of the local wheels with the
  workbench and DuckDB extras selected Pillow 13.0.0; package consistency,
  `pip-audit` of published packages, workbench imports and profiling HTML generation passed.
  This is a smoke test, not the full Python 3.11 matrix.
- Ruff, format and lockfile checks passed. A workbench server and Docusaurus
  server answered local health requests; a profiling report rendered HTML.
- Basedpyright on Python 3.14 reported zero errors and 1982 warnings; the
  unchanged upstream snapshot produced zero errors and 1981 warnings in the
  same environment. Warnings have not been remediated.
- `pip-audit` reported no known vulnerabilities in the published packages in
  the Python 3.14 test environment; both local fork builds were not auditable
  via PyPI. The Python 3.10 workbench finding is recorded above.
- The docs npm audit reports five low-severity dependency-chain findings caused
  by `deepmerge`; the upstream version has no non-vulnerable 4.x release.

To reproduce the local Python 3.14 test environment from these two adjacent
checkouts, run the following from the dbt-osmosis checkout. This is a local
development procedure, not a published or independently installable release:

```bash
UV_PROJECT_ENVIRONMENT=/tmp/dbt-osmosis-fork-env uv sync --locked --python 3.14 --all-extras
uv pip install --python /tmp/dbt-osmosis-fork-env/bin/python --no-deps -e ../dbt-core-interface
uv pip check --python /tmp/dbt-osmosis-fork-env/bin/python
```

## Known limitations

- Published `dbt-core-interface` 1.1.7 declares Python `<3.14`. A separate local
  interface patch was tested with dbt Core 1.12, but this project still resolves
  the upstream distribution until a patched fork is available and wired in.
  Python 3.14 installations and the Python 3.14 CI matrix jobs are therefore
  not yet supported for release.
- The workbench's pinned fork version in `requirements.txt` requires that build
  to be published to an accessible package index before Streamlit deployment.
- npm audit reports `deepmerge` 4.3.1, an indirect Docusaurus build dependency,
  for GHSA-gcqx-w48m-w2h4 (low). There is no fixed release in the affected 4.x
  line; do not feed untrusted objects into the build or development server.
- A Bandit scan flags generated SQL assembled from model and column names. Some
  findings describe SQL sent as LLM context, while staging generation produces
  executable SQL for later use. Generated output and its inputs still require
  review before execution; the scan is not a complete security assessment.
- External formatter configuration executes a local program with the caller's
  permissions; only use formatter commands from trusted project configuration.
