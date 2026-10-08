"""Compose hook: register the staged v2 routes in the shared application (B04).

The plan registers the staged v2 app inside the shared application without
removing or shadowing any legacy route, keeping path ordering and operation
IDs. ``include_router`` alone gets four things wrong, each measured against a
synthetic host before this module was written:

* the staged error envelopes live in the staged app's ``exception_handlers``,
  and FastAPI copies that mapping into its middleware stack when the stack is
  first built, so a raw include serves legacy-shaped 404s and plain-text 500s
  for v2 paths;
* FastAPI merges a default ``application/json`` entry into every operation's
  success response, which the staged app's own document wrapper drops for the
  binary rows but the host document keeps;
* a late attach (after the first request) cannot take effect at all, because
  the handler snapshot is already taken;
* a scoped wrapper for ``Exception`` becomes the host's server-error handler
  (FastAPI moves that key into ``ServerErrorMiddleware``), so for a non-v2
  path it must return the framework's own default response; merely re-raising
  there turns a legacy plain-text 500 into an empty one.

So this hook re-installs the staged handlers *scoped to the v2 prefix*, wraps
the host document with the same binary transform, and refuses to run twice or
after the host has started serving. Every non-v2 path keeps the host's own
handlers untouched, down to its default unhandled-error bytes.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import WebSocketRequestValidationError
from starlette.responses import PlainTextResponse

from . import links
from .app import create_app

#: Host state marker set once the staged app is attached.
_ATTACHED = "_examdata_v2_attached"

#: Staged handlers this hook does not re-install: the staged app never
#: registers a websocket route, so the default stays exactly as the host had it.
_HANDLER_SKIP: tuple[type, ...] = (WebSocketRequestValidationError,)


async def _resolve(handler: Callable[..., Any], request: Request,
                   exc: Exception) -> Any:
    response = handler(request, exc)
    if inspect.isawaitable(response):
        response = await response
    return response


def _default_server_error(request: Request, exc: Exception) -> PlainTextResponse:
    """The response the host would have produced without a server-error handler.

    Installing a scoped ``Exception`` wrapper makes it the host's server-error
    handler, so a non-v2 path must answer exactly like the framework default:
    a plain-text 500. Re-raising instead sends nothing and changes the legacy
    bytes.
    """
    return PlainTextResponse("Internal Server Error", status_code=500)


def _scoped_handler(v2_handler: Callable[..., Any],
                    prior_handler: Callable[..., Any] | None,
                    fallback: Callable[..., Any] | None = None
                    ) -> Callable[..., Any]:
    """One host handler answering v2 paths from the staged app's handler.

    Non-v2 requests fall through to whatever the host had registered before
    the composition; ``None`` means "not handled here", in which case the
    original exception is re-raised -- or answered by ``fallback``, which the
    server-error slot uses to keep the framework default -- so the host's
    behaviour (and its bytes) stay exactly as they were.
    """
    async def scoped(request: Request, exc: Exception) -> Any:
        path = request.url.path
        if path == links.PREFIX or path.startswith(links.PREFIX + "/"):
            return await _resolve(v2_handler, request, exc)
        if prior_handler is not None:
            return await _resolve(prior_handler, request, exc)
        if fallback is not None:
            return fallback(request, exc)
        raise exc
    return scoped


def _apply_binary_media(document: dict[str, Any]) -> None:
    """Drop the default ``application/json`` from binary success rows.

    Mirrors the staged app's own document transform in ``create_app``; that
    one is local to the factory, so the loop over the binary rows is repeated
    here against the composed document.
    """
    for row in links.ROUTE_SPECS:
        if not row.binary:
            continue
        for method in ("get", "head"):
            operation = document.get("paths", {}).get(row.full_path, {}).get(method)
            if not operation:
                continue
            for code in ("200", "206"):
                content = operation.get("responses", {}).get(code, {}).get("content")
                if content:
                    content.pop("application/json", None)


def attach_v2(host: FastAPI, *, application: FastAPI | None = None) -> FastAPI:
    """Register the staged v2 app inside ``host`` and return ``host``.

    Must be called before the host serves its first request. Refuses a
    non-FastAPI host, a second attach, and a late attach; every refusal
    happens before the host is modified.
    """
    if not isinstance(host, FastAPI):
        raise TypeError("attach_v2 expects a FastAPI application")
    if getattr(host.state, _ATTACHED, False):
        raise RuntimeError("the staged v2 app is already attached to this host")
    if host.middleware_stack is not None:
        raise RuntimeError(
            "attach_v2 must be called before the host serves its first "
            "request: the middleware stack snapshots the exception handlers "
            "when it is built")

    v2 = application if application is not None else create_app()
    host.include_router(v2.router)  # appended: the host's own order is kept

    prior = dict(host.exception_handlers)
    for exc_class, v2_handler in v2.exception_handlers.items():
        if exc_class in _HANDLER_SKIP:
            continue
        fallback = _default_server_error if exc_class is Exception else None
        host.add_exception_handler(
            exc_class, _scoped_handler(v2_handler, prior.get(exc_class),
                                       fallback=fallback))

    host.openapi_schema = None  # rebuild from the composed route table
    framework_openapi = host.openapi

    def _composed_openapi() -> dict[str, Any]:
        document = framework_openapi()
        _apply_binary_media(document)
        return document

    host.openapi = _composed_openapi  # instance attribute shadows the method

    setattr(host.state, _ATTACHED, True)
    host.state.examdata_v2_app = v2
    return host


__all__ = ["attach_v2"]
