# Workspace source snapshot

The main branch now also contains the integrated package at `src/examdata/integration/` and a unified launcher. See [the main integration guide](docs/MAIN_INTEGRATION.md) and [validation limits](docs/integration/MAIN_MERGE_VALIDATION.md). Historical staging copies remain for provenance.

The repository root contains the examdata Python project. Sibling workspace modules are included in directories frontend/, web/, ielts-api/, toefl-api/, integration-staging/, ielts-data/, cie-location-batch/, and other source directories. Original sibling paths were copied without modifying the running workspace.

Dependencies, downloaded exam papers, audio, databases, runtime output, caches, large generated datasets, and local credentials are excluded. Investigation scripts are retained as source. Some scripts assume the original workspace sibling layout; configure paths before running.
