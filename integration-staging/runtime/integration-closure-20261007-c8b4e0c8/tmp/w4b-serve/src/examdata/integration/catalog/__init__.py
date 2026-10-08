"""Staged catalog and revision publication (plan 7.2, 7.3; packet A09).

This package is the private mapping/catalog store plus the revision publisher:

* :mod:`examdata.integration.catalog.model` - ``CatalogSource`` (one mapping
  input), ``CatalogEntry`` (one stored row) and ``CatalogSnapshot`` (an immutable
  revision body);
* :mod:`examdata.integration.catalog.store` - ``CatalogStore``: register a native
  identity, derive its stable public ID, detect duplicate native ids, identity
  collisions and alias conflicts, and validate cross-references;
* :mod:`examdata.integration.catalog.builder` - ``CatalogBuilder``: build a
  snapshot from staged fixtures only, validate identities/references/counts, diff
  it against the previous revision and reject unexplained removals or quality
  upgrades without evidence;
* :mod:`examdata.integration.catalog.revision` - ``RevisionPublisher``: write an
  immutable revision file, atomically replace a small versioned ``current.json``
  pointer (no symlink privileges), keep the previous revision for rollback and
  active cursors, and bind/validate cursors.

Import the submodules directly (``from examdata.integration.catalog.store import
CatalogStore``); this ``__init__`` deliberately imports nothing so it can never
create an import cycle with the frozen A04/A07/A08 modules. Stdlib only. Nothing
here reads the original project, the network, or a database.
"""
