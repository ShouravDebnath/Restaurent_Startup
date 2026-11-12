import re

from .test_security import routes


def test_every_resource_route_has_negative_security_coverage(suite):
    def normalize(path):
        path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{id}", path)
        return re.sub(r"\{[^}]+\}", "{id}", path)

    covered = {(method, normalize(path)) for method, path, _ in routes(suite.seed, "a")}
    covered |= {
        ("GET", "/v1/me"),
        ("GET", "/v1/auth/csrf"),
        ("DELETE", "/v1/auth/session"),
        ("GET", "/v1/organizations"),
        ("POST", "/v1/organizations"),
    }
    public = {("POST", "/v1/auth/session"), ("GET", "/v1/demo/tenant"), ("POST", "/v1/edge/pairings")}
    # Every Phase 3 route below is exercised anonymously and in both tenant directions
    # by test_dashboard.py::test_dashboard_routes_reject_foreign_and_anonymous_access.
    covered |= {
        ("GET", "/v1/locations/{id}/dashboard"),
        ("GET", "/v1/locations/{id}/tasks"),
        ("GET", "/v1/locations/{id}/activity"),
        ("GET", "/v1/locations/{id}/stream"),
        ("POST", "/v1/locations/{id}/demo/events"),
        ("POST", "/v1/tables/{id}/actions"),
    }
    actual = {
        (method.upper(), normalize(path))
        for path, operations in suite.app.openapi()["paths"].items()
        if path.startswith("/v1/")
        for method in operations
        if method in {"get", "post", "patch", "put", "delete"}
    }
    # Both-direction/anonymous cases are in test_calibration.py.
    covered |= {
        ("POST", "/v1/locations/{id}/cameras/{id}/preview-grants"),
        ("GET", "/v1/locations/{id}/cameras/{id}/preview-grants"),
        ("POST", "/v1/locations/{id}/cameras/{id}/preview-grants/{id}/revoke"),
        ("GET", "/v1/locations/{id}/cameras/{id}/preview-authorization"),
        ("GET", "/v1/locations/{id}/table-zones/{id}/revisions"),
    }
    # HTTPS/no-signature and both-tenant/anonymous cases: test_edge_transport.py.
    covered |= {
        ('POST', '/v1/edge/pairings/proof'), ('POST', '/v1/edge/batches'), ('POST', '/v1/edge/events'),
        ('POST', '/v1/edge/heartbeat'),
        ('GET', '/v1/locations/{id}/devices'), ('POST', '/v1/locations/{id}/devices/commands'),
    }
    # Both-tenant/anonymous/role negatives are exercised by Phase 7 workflow/report tests.
    covered |= {
        ('GET','/v1/locations/{id}/workflow'), ('GET','/v1/locations/{id}/workflow-suggestions'),
        ('GET','/v1/locations/{id}/workflow-policy'), ('PUT','/v1/locations/{id}/workflow-policy'),
        ('POST','/v1/locations/{id}/workflow-suggestions/{id}/decisions'),
        ('POST','/v1/tables/{id}/workflow-actions'), ('GET','/v1/locations/{id}/analytics'),
        ('GET','/v1/locations/{id}/analytics.csv'),
    }
    assert actual == covered | public
