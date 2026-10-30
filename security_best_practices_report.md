# Security review: dbt-osmosis fork

## Summary

This is a focused local review, not a penetration test or certification. The
project is primarily a Python CLI with a Streamlit workbench; its documentation
uses Docusaurus and React. Review covered selected file-write, Jinja, SQL,
subprocess and frontend sinks, Bandit findings, and dependency audit results.
The available security skill has React and general frontend guidance but no
Python/Streamlit-specific reference. Results are local and do not establish the
security of a deployed server, upstream services, or every code path.

## High: unresolved deployment risk

### 0. Python 3.10 workbench installs a vulnerable Pillow release

In a fresh Python 3.10.20 wheel installation with the workbench extra,
`pip-audit` reported 39 advisory IDs for Pillow 12.3.0. At least one,
[GHSA-78g4-xqwv-q3g8](https://github.com/advisories/GHSA-78g4-xqwv-q3g8),
describes a high-severity image-decoding issue and lists Pillow 13.0.0 as the
fix. [Pillow 13.0.0 requires Python 3.11 or newer](https://pypi.org/project/pillow/13.0.0/).
The local fork now omits workbench dependencies on Python 3.10 and rejects
the workbench command there; Python 3.11 or newer is required for the workbench
and its metadata requires Pillow 13 or newer. The vulnerable result above was
obtained from the earlier wheel, before this change. The two local fork wheels
were not audited via PyPI. A separate Python 3.10 installation without the
workbench extra had no known published package vulnerabilities in the same audit.

### 1. Interface API can execute SQL without built-in authentication

The interface FastAPI application exposes `/api/v1/run`, which compiles and
executes SQL against a registered project, and no authentication dependency is
visible in its application or endpoint configuration. Its command-line
default binds to `127.0.0.1`, but upstream documentation recommended binding to
`0.0.0.0`. The local fork documentation now recommends localhost and states
the lack of authentication. Do not expose this service to untrusted networks;
remote use requires independently verified authentication and network access
controls. Localhost does not protect against other local processes. A local
test showed that a foreign-origin text/plain request previously reached the
SQL execution path; the fork now rejects untrusted browser Origins and
browser-marked cross-site requests. A live localhost smoke test returned HTTP
403 for a foreign Origin and HTTP 200 for the local Origin. This does not authenticate clients and
does not protect against non-browser clients or browsers omitting those
headers. See
`dbt-core-interface/src/dbt_core_interface/server.py:225`, `:232`, `:350`, `:1621`,
and `dbt-core-interface/README.md`. No remote deployment was inspected.

## High: addressed locally

### 2. Generated staging filenames could escape the intended directory

AI-generated `staging_name` was incorporated into output paths, and the legacy
staging writer could write those paths. A malicious or malformed model name
could therefore direct a write outside the intended staging directory when a
user chose to write generated files. The two path builders now reject path
separators, drive syntax and existing targets resolving outside the directory;
default staging directories are also checked against the project root. The
legacy writer rechecks targets before writing either file. See
`src/dbt_osmosis/core/staging.py:141`, `:157`, `:332`, and
`src/dbt_osmosis/core/generators.py:76`.

Tests cover traversal, absolute paths, Windows-style paths, existing symlinks,
and targets changed to symlinks between generation and writing. These checks
do not guarantee safety against a concurrent adversary changing filesystem
links between the final check and the write; use a trusted project directory.

### 3. Generated Jinja arguments could break out of string literals

Source names and materialization values were interpolated directly into Jinja
string literals. The local change escapes them as string literals, and a Jinja
rendering regression test exercises malicious quote-containing values for
source, model and seed references. See `src/dbt_osmosis/core/llm.py:1318` and
`tests/core/test_staging_sql_literals.py`.

## Medium: remaining trust boundary

### 4. Webhook destinations are configurable by server callers

The interface API can create webhook alert channels from caller-provided
configuration (`dbt-core-interface/src/dbt_core_interface/server.py:1086`),
and the channel sends HTTP requests to the configured URL
(`dbt-core-interface/src/dbt_core_interface/quality.py:263`). There is no
destination allowlist visible in these paths. An untrusted caller who can
configure and trigger alerts may induce outbound requests, including to
internal addresses. Restrict who can access the API and constrain network
egress; private webhook destinations may be legitimate, so no destination
policy has been assumed or silently imposed. No live network probe was made.

### 5. Interface source introspection constructs SQL from names

The locally patched `dbt-core-interface` source generator previously embedded
schema exclusions and table/schema names in SQL that was compiled as Jinja.
The local patch disables Jinja compilation for these metadata queries and
rejects unsafe literal values and database identifiers before execution. It
deliberately rejects some valid special-character names, and has only been
tested against DuckDB, not live PostgreSQL, Redshift, Databricks, Snowflake or
BigQuery. Other SQL generation paths in the interface remain to be reviewed.
See the separate `dbt-core-interface/FORK_CHANGES.md` and
`src/dbt_core_interface/source_generator.py`.

### 6. Generated SQL and Jinja expressions require human review

`ColumnTransformation` intentionally accepts SQL expressions and emits them
into a model (`src/dbt_osmosis/core/llm.py:1288`); generated SQL can also be
executed via an explicit CLI option (`src/dbt_osmosis/cli/main.py:1144`).
Escaping names does not make an AI-produced SQL expression safe or prevent Jinja
inside that expression from being interpreted by dbt. Review generated models
and SQL before writing, compiling or executing them, and use least-privilege
warehouse credentials. No live adversarial LLM or warehouse test was performed.
The interface's built-in quality checks now validate simple column names and
numeric bounds and escape model references. Custom SQL checks deliberately
remain executable SQL and must be configured only by trusted users.

### 7. AI descriptions could alter generated YAML

The legacy staging YAML generator previously interpolated descriptions inside
quoted YAML text. It now uses a ruamel round-trip serializer so quotes and
newlines remain scalar data (`src/dbt_osmosis/core/staging.py:378`). A regression
test checks that a description resembling an injected `config` mapping is
preserved exactly, including column descriptions.

### 8. Interface source YAML could reinterpret descriptions as YAML

The interface source generator previously assembled YAML by interpolating
database names, descriptions and metadata into text. It now builds a data
structure and serializes it with a safe YAML dumper; tests check that hostile
descriptions remain scalar values and that multiple sources share one valid
document. See `dbt-core-interface/src/dbt_core_interface/source_generator.py:572`.
This changes textual formatting while preserving the represented fields.

### 9. Existing SQL could be silently overwritten during generation

The model and staging CLI flows previously checked YAML overwrite permission
but wrote SQL with truncation even without `--overwrite`. They now refuse an
existing SQL file unless `--overwrite` is provided; exclusive file creation
also catches a conflicting file created after the initial check. Regression
tests verify both commands leave the existing SQL and prospective YAML intact
on refusal and permit the explicit overwrite. The legacy `write_staging_files`
API likewise requires `overwrite=True` to replace either output. Two-file writes
are not a transaction, so interruption or a concurrent filesystem change can
still leave partial output.

## Low: unresolved dependency finding

### 10. Documentation build uses affected deepmerge 4.x

The last local npm audit reported five low-severity dependency-chain entries
caused by `deepmerge` 4.3.1 and GHSA-gcqx-w48m-w2h4. No fixed 4.x release was
available at the time. Avoid passing untrusted objects to the documentation
build/development server and revisit the upstream dependency when a compatible
fix is available. Docusaurus also uses a tested but unsupported `tinypool` 2.x
override (`docs/package.json:34`); its production build and a local development
server were smoke-tested, not exhaustively tested.

## Operational trust boundaries and verification limits

- An external formatter is deliberately executed as a subprocess from project
  configuration (`src/dbt_osmosis/core/formatting.py:35`); formatter commands
  and project configuration must be trusted. Arguments are passed as a list.
- The local interface fork no longer writes webhook URLs or HTTP exception
  messages to its own alert-channel logs. Third-party HTTP debug logging can
  have separate disclosure risks and should be configured accordingly.
- The workbench defaults to localhost and the external feed is opt-in
  (`src/dbt_osmosis/cli/main.py:1650`); deployments exposed beyond localhost
  need separately verified access controls and network protections.
- Python 3.14 and 3.11 workbench audits found no known vulnerabilities in the
  installed published packages; the Python 3.10 workbench finding is described
  above. The audits could not evaluate either locally modified fork version
  against PyPI. Some transitive versions remain constrained by dbt and profiling
  dependencies.
- The full project suite passed 1009 tests with six skips and 75.31% coverage
  after the local interface and Python 3.10 workbench changes, below the
  requested 100%. This does not validate every attack path.
