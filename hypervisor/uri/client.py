from __future__ import annotations

from urllib.parse import urlparse

from uri3.graph.uri_graph import build_graph_from_tree
from uri3.logs.reader import read_logs, summarize_logs
from uri3.resolvers.router import Uri3Router, UriResolution
from uri3.scanner.scanner import scan

_OPERATOR_SCHEMES = frozenset(
    {"browser", "dom", "screen", "input", "android", "pcwin", "robot", "device"}
)


class Uri3Client:
    """Thin hypervisor adapter over uri3 routing, scanning and graph utilities."""

    def __init__(self):
        self.router = Uri3Router()

    def resolve(self, uri: str) -> UriResolution | dict:
        return self.router.resolve(uri)

    def call(
        self,
        uri: str,
        payload: dict | None = None,
        *,
        approved: bool = False,
        environment: str | None = None,
    ):
        if urlparse(uri).scheme in _OPERATOR_SCHEMES:
            from hypervisor.routing import call_uri

            return call_uri(
                uri,
                payload or {},
                approved=approved,
                environment=environment,
            ).to_dict()
        return self.router.call(uri, payload)

    def explain(self, uri: str, payload: dict | None = None):
        from uri3.resolvers.explain import explain_uri

        body = explain_uri(uri)
        if urlparse(uri).scheme in _OPERATOR_SCHEMES:
            from hypervisor.routing import resolve_hypervisor_route

            body["hypervisor_resolution"] = resolve_hypervisor_route(
                uri,
                payload=payload or {},
            ).to_dict()
        return body

    def scan(self, uri: str):
        return scan(uri)

    def logs(self, uri: str, *, summary: bool = False):
        return summarize_logs(uri) if summary else read_logs(uri)

    def schema(self, target: str):
        from uri3.protocols.scheme_registry import describe_uri

        return describe_uri(target)

    def graph(self, path: str):
        return build_graph_from_tree(path)

    def nl2uri(self, prompt: str):
        from nl2uri.planner import rule_based_plan

        return rule_based_plan(prompt).tree
