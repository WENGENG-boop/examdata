"""Staged Phase A integration package (plan section 3.5).

Phase A builds the integrated v2 components only inside this package, under
`integration-staging/src/examdata.integration/`. Nothing here is merged into the
original tree; final module names are chosen in Phase B.

Module families (added by later packets):
    contracts/     models, schemas, identifiers, quality rules        (A04)
    providers/     protocol, registry, fixture-backed wrappers        (A05)
    services/      catalog, resources, questions, answers, coverage
    runtime/       configuration, component manifest, Node runner     (A06)
    catalog/       stable mappings and published read index           (A09)
    api/           isolated v2 application factory                    (A10)
    operations/    read-only checkpoint adapters and coverage
    observability/ request context and structured events
    testing/       staging harness support (guards; not product code)
"""

__version__ = "0.0.0-phasea"
