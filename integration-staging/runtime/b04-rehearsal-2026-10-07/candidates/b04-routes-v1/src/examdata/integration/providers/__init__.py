"""Staged provider layer (plan 3.5, A05).

Public surface:

* `capabilities`  - the ten read capabilities and availability states;
* `protocol`      - `Provider` protocol and `ProviderDescriptor`;
* `results`       - typed `ProviderResult` / `DispatchResult` (no fake empties);
* `registry`      - `ProviderRegistry`: capability filtering, alias routing, dispatch;
* `fixtures`      - CIE/Edexcel/IELTS synthetic-fixture providers plus edge providers.

Nothing in this package reads the original project, the network, or the live
database; providers accept only fixtures labelled synthetic.
"""
from .capabilities import CAPABILITIES, TARGET_REQUIRED, Availability, Capability
from .fixtures import (
    CIEIndexProvider,
    EdexcelIndexProvider,
    FailingProvider,
    FixtureProvider,
    IELTSQuestionsProvider,
    NullProvider,
    UnavailableProvider,
)
from .protocol import Provider, ProviderDescriptor
from .registry import (
    AliasRoutingError,
    DuplicateProviderError,
    ProviderRegistry,
    ProviderRegistryError,
    UnknownAliasError,
    UnknownProviderError,
)
from .results import DispatchResult, ERROR_PRECEDENCE, OutcomeStatus, ProviderResult

__all__ = [
    "Capability",
    "CAPABILITIES",
    "TARGET_REQUIRED",
    "Availability",
    "Provider",
    "ProviderDescriptor",
    "ProviderResult",
    "DispatchResult",
    "OutcomeStatus",
    "ERROR_PRECEDENCE",
    "ProviderRegistry",
    "ProviderRegistryError",
    "DuplicateProviderError",
    "UnknownProviderError",
    "AliasRoutingError",
    "UnknownAliasError",
    "FixtureProvider",
    "CIEIndexProvider",
    "EdexcelIndexProvider",
    "IELTSQuestionsProvider",
    "NullProvider",
    "UnavailableProvider",
    "FailingProvider",
]
