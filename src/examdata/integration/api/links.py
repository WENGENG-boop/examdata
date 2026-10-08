"""The single v2 route registry (plan 5.4).

One row per route the plan proposes, in the plan's order. Every row is
implemented since packet A11 staged the binary transport (plan 5.3): the five
content/crop rows are registered with the media types they serve, and a link
is only emitted for an entity whose verified sample actually exists, so a link
can never claim an unavailable feature.

`app.py` registers exactly the implemented rows, and `openapi.py` asserts the
runtime route table, the OpenAPI document and this registry all agree.
"""
from __future__ import annotations

from dataclasses import dataclass

PREFIX = "/api/v2"


@dataclass(frozen=True)
class RouteSpec:
    capability: str
    method: str
    path: str
    implemented: bool
    deferred_reason: str | None = None
    binary: bool = False
    media_types: tuple[str, ...] = ()

    @property
    def full_path(self) -> str:
        return PREFIX + self.path

    def to_dict(self) -> dict[str, object]:
        row: dict[str, object] = {"capability": self.capability, "method": self.method,
                                  "path": self.full_path}
        if self.deferred_reason:
            row["deferred_reason"] = self.deferred_reason
        if self.media_types:
            row["media_types"] = list(self.media_types)
        return row


def _r(capability: str, path: str, *, implemented: bool = True,
       deferred_reason: str | None = None, binary: bool = False,
       media_types: tuple[str, ...] = ()) -> RouteSpec:
    return RouteSpec(capability=capability, method="GET", path=path,
                     implemented=implemented, deferred_reason=deferred_reason,
                     binary=binary, media_types=media_types)


#: Plan 5.4, in the plan's order.
ROUTE_SPECS: tuple[RouteSpec, ...] = (
    _r("info", "/info"),
    _r("exam-systems", "/exam-systems"),
    _r("providers", "/providers"),
    _r("courses.list", "/courses"),
    _r("courses.get", "/courses/{id}"),
    _r("syllabuses.list", "/syllabuses"),
    _r("syllabuses.get", "/syllabuses/{id}"),
    _r("syllabuses.content", "/syllabuses/{id}/content", binary=True,
       media_types=("application/pdf", "image/png")),
    _r("containers.list", "/containers"),
    _r("containers.get", "/containers/{id}"),
    _r("containers.resources", "/containers/{id}/resources"),
    _r("containers.questions", "/containers/{id}/questions"),
    _r("resources.list", "/resources"),
    _r("resources.get", "/resources/{id}"),
    _r("resources.content", "/resources/{id}/content", binary=True,
       media_types=("application/pdf", "image/png")),
    _r("questions.list", "/questions"),
    _r("questions.get", "/questions/{id}"),
    _r("questions.answers", "/questions/{id}/answers"),
    _r("questions.regions", "/questions/{id}/regions"),
    _r("questions.crop", "/questions/{id}/crop", binary=True,
       media_types=("image/png",)),
    _r("questions.audio", "/questions/{id}/audio"),
    _r("assets.get", "/assets/{id}"),
    _r("assets.content", "/assets/{id}/content", binary=True,
       media_types=("application/pdf", "image/png")),
    _r("tags.list", "/tags"),
    _r("tags.questions", "/tags/{id}/questions"),
    _r("materials.list", "/materials"),
    _r("materials.get", "/materials/{id}"),
    _r("materials.content", "/materials/{id}/content", binary=True,
       media_types=("application/pdf", "image/png")),
    _r("timetables.list", "/timetables"),
    _r("timetables.events", "/timetables/events"),
    _r("timetables.windows", "/timetables/windows"),
    _r("coverage.get", "/coverage"),
    _r("gaps.list", "/gaps"),
    _r("jobs.get", "/jobs/{id}"),
)

IMPLEMENTED_SPECS: tuple[RouteSpec, ...] = tuple(s for s in ROUTE_SPECS if s.implemented)
DEFERRED_SPECS: tuple[RouteSpec, ...] = tuple(s for s in ROUTE_SPECS if not s.implemented)


def advertised() -> list[dict[str, object]]:
    """The links `GET /api/v2/info` may publish: implemented routes only."""
    return [spec.to_dict() for spec in IMPLEMENTED_SPECS]


def advertised_pairs() -> frozenset[tuple[str, str]]:
    return frozenset((s.method, s.full_path) for s in IMPLEMENTED_SPECS)


def deferred() -> list[dict[str, object]]:
    return [spec.to_dict() for spec in DEFERRED_SPECS]


def spec_for(capability: str) -> RouteSpec:
    for spec in ROUTE_SPECS:
        if spec.capability == capability:
            return spec
    raise KeyError(capability)


def entry_links(kind: str, public_id: str, *, content_available: bool = False,
                crop_available: bool = False) -> dict[str, str]:
    """Links for one entity, restricted to routes that can serve it.

    Every route here is implemented; the content and crop links are emitted
    only when the entity has a matching verified sample, so a caller can never
    follow a link into an unavailable feature.
    """
    links: dict[str, str] = {}
    if kind == "course":
        links["self"] = f"{PREFIX}/courses/{public_id}"
    elif kind == "container":
        links["self"] = f"{PREFIX}/containers/{public_id}"
        links["resources"] = f"{PREFIX}/containers/{public_id}/resources"
        links["questions"] = f"{PREFIX}/containers/{public_id}/questions"
    elif kind == "question":
        links["self"] = f"{PREFIX}/questions/{public_id}"
        links["answers"] = f"{PREFIX}/questions/{public_id}/answers"
        links["regions"] = f"{PREFIX}/questions/{public_id}/regions"
        links["audio"] = f"{PREFIX}/questions/{public_id}/audio"
        if crop_available:
            links["crop"] = f"{PREFIX}/questions/{public_id}/crop"
    elif kind == "asset":
        links["self"] = f"{PREFIX}/assets/{public_id}"
        links["resource"] = f"{PREFIX}/resources/{public_id}"
        if content_available:
            links["content"] = f"{PREFIX}/assets/{public_id}/content"
    return links


__all__ = [
    "PREFIX",
    "RouteSpec",
    "ROUTE_SPECS",
    "IMPLEMENTED_SPECS",
    "DEFERRED_SPECS",
    "advertised",
    "advertised_pairs",
    "deferred",
    "spec_for",
    "entry_links",
]
