# Staging configuration (Phase A, packet A06)

Two example inputs for the single resolver in
`src/examdata_integration/runtime/settings.py`. Neither file is read at import
time and neither points at the original tree, the live database, or an upstream
host.

- `staging.env.example` — the environment template from `env_template()`. Every
  line is commented out; copy it into a private file and source it in a child
  process. Do not mutate the user environment.
- `staging-config.example.json` — the same settings as a JSON config file. The
  object keys are canonical setting keys (`node_executable`, `network_mode`, …),
  not environment variable names. A `PATH` value is made absolute against the
  process working directory, so run the process from the staging root when using
  relative paths.

## Precedence (plan 6.1, fixed)

1. explicit argument (`resolve_config(explicit=...)`)
2. process environment (`EXAMDATA_*`, plus the legacy aliases)
3. config file (`config_file=...`, must live inside the staging tree)
4. manifest defaults (`manifest_defaults=...`)
5. built-in default from `SETTING_SPECS`

A setting is taken from the highest layer that supplies a non-empty value. The
resolver records `source` and `origin` per setting so a report can always say
where a value came from. Legacy aliases (`IELTS_API_DIR`, `TOEFL_API_DIR`) still
work but emit a deprecation warning; if an alias and its canonical name disagree,
resolution fails with `ConfigConflictError` rather than picking one silently.
