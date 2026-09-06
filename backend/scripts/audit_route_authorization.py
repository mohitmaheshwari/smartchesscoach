#!/usr/bin/env python3
"""Enumerate EVERY HTTP route and assert its authorization posture.

WHY THIS EXISTS

Reviews of this codebase have been exploratory: someone looks where their
attention goes and reports what they find. That can always surface something
new, so the score never converges and fixing findings never finishes the job.
An unauthenticated admin download route survived that way -- not because it was
hard to see, but because nobody had looked at that particular file yet.

This replaces judgement with enumeration. Every route decorator in the
codebase is matched to its handler, the handler's parameters are read for an
auth dependency, and anything reachable without authentication must appear in
PUBLIC_ROUTES below with a stated reason. A new unauthenticated route fails
the audit the moment it is added.

The point is the denominator. "We found some issues" becomes "N routes were
checked, M are public, all M are declared."

Usage:
    python backend/scripts/audit_route_authorization.py            # human
    python backend/scripts/audit_route_authorization.py --json     # machine
Exit code 1 if any undeclared public route exists.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parent.parent

# Dependencies that establish an authenticated caller.
AUTH_DEPENDENCIES = {
    "get_current_user",
    "require_admin",
    "require_super_admin",
}
# Dependencies that establish an ADMIN caller specifically.
ADMIN_DEPENDENCIES = {"require_admin", "require_super_admin"}
# Optional auth: caller may be anonymous, so the route is effectively public.
OPTIONAL_AUTH = {"get_current_user_optional"}

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}

# Routes that are intentionally reachable without authentication.
# Every entry needs a reason. Adding one is a deliberate act, reviewable in
# the diff, which is the entire point -- a route cannot become public silently.
PUBLIC_ROUTES: dict[str, str] = {
    "GET /api/health": "liveness probe; no data",
    "GET /health": "liveness probe; no data",
    "POST /api/auth/login": "establishes a session",
    "POST /api/auth/register": "creates an account",
    "GET /api/auth/dev-login": "dev-mode only; gated by DEV_MODE",
    "GET /api/auth/google": "OAuth redirect",
    "GET /api/auth/google/callback": "OAuth callback",
    "POST /api/auth/logout": "clears a session",
    "GET /api/auth/me": "returns 401 when anonymous; the auth probe itself",
}


def _decorator_route(node: ast.AST) -> tuple[str, str] | None:
    """Return (METHOD, path) if this decorator is a route registration."""
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if not isinstance(func, ast.Attribute) or func.attr not in HTTP_METHODS:
        return None
    owner = func.value
    owner_name = getattr(owner, "id", None) or getattr(owner, "attr", None)
    if owner_name not in {"router", "app"}:
        return None
    if not node.args:
        return None
    first = node.args[0]
    if not isinstance(first, ast.Constant) or not isinstance(first.value, str):
        return None
    return func.attr.upper(), first.value


def _depends_names(fn: ast.AST) -> set[str]:
    """Every name passed to Depends(...) anywhere in the signature."""
    found: set[str] = set()
    args = getattr(fn, "args", None)
    if args is None:
        return found
    defaults = list(args.defaults) + [d for d in args.kw_defaults if d is not None]
    for default in defaults:
        for sub in ast.walk(default):
            if (
                isinstance(sub, ast.Call)
                and getattr(sub.func, "id", None) == "Depends"
                and sub.args
            ):
                target = sub.args[0]
                name = getattr(target, "id", None) or getattr(target, "attr", None)
                if name:
                    found.add(name)
    # Annotated[...] style dependencies
    for arg in list(args.args) + list(args.kwonlyargs):
        if arg.annotation is not None:
            for sub in ast.walk(arg.annotation):
                if (
                    isinstance(sub, ast.Call)
                    and getattr(sub.func, "id", None) == "Depends"
                    and sub.args
                ):
                    target = sub.args[0]
                    name = getattr(target, "id", None) or getattr(target, "attr", None)
                    if name:
                        found.add(name)
    return found


# Some handlers take Depends(get_current_user) and then assert admin INSIDE the
# body. That is a real gate the signature cannot show, and treating it as a
# finding would fill the report with false positives -- which is how gates get
# muted and stop being run at all.
IN_BODY_ADMIN_ASSERTIONS = {
    "_ensure_authenticated_admin",
    "ensure_authenticated_admin",
    "_require_admin",
    "require_admin",
    "_assert_admin",
    "assert_admin",
}


def _asserts_admin_in_body(fn: ast.AST) -> str | None:
    """Name of an admin assertion called inside the handler body, if any."""
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in IN_BODY_ADMIN_ASSERTIONS:
                return name
    return None


def _router_prefix(tree: ast.AST) -> str:
    """APIRouter(prefix="/x") if declared at module level."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "APIRouter":
            for kw in node.keywords:
                if kw.arg == "prefix" and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    return ""


def audit() -> dict:
    files = sorted(BACKEND.glob("routes/*.py")) + [BACKEND / "server.py"]
    routes = []
    for path in files:
        if not path.exists():
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        prefix = _router_prefix(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in node.decorator_list:
                route = _decorator_route(dec)
                if not route:
                    continue
                method, raw_path = route
                deps = _depends_names(node)
                body_admin = _asserts_admin_in_body(node)
                authed = bool(deps & AUTH_DEPENDENCIES)
                admin = bool(deps & ADMIN_DEPENDENCIES) or bool(body_admin)
                optional = bool(deps & OPTIONAL_AUTH)
                full = raw_path if raw_path.startswith("/api") else f"/api{prefix}{raw_path}"
                routes.append({
                    "method": method,
                    "path": full,
                    "key": f"{method} {full}",
                    "file": path.relative_to(BACKEND.parent).as_posix(),
                    "line": node.lineno,
                    "handler": node.name,
                    "authenticated": authed,
                    "admin_only": admin,
                    "admin_via_body_check": body_admin,
                    "optional_auth": optional,
                    "dependencies": sorted(deps),
                })

    public = [r for r in routes if not r["authenticated"]]
    undeclared = [r for r in public if r["key"] not in PUBLIC_ROUTES]
    # An admin-PATH route that is not admin-gated is the sharpest failure.
    admin_path_unguarded = [
        r for r in routes
        if "/admin" in r["path"] and not r["admin_only"]
    ]
    return {
        "total_routes": len(routes),
        "authenticated": sum(1 for r in routes if r["authenticated"]),
        "admin_only": sum(1 for r in routes if r["admin_only"]),
        "public": len(public),
        "declared_public": len(public) - len(undeclared),
        "undeclared_public": undeclared,
        "admin_path_not_admin_gated": admin_path_unguarded,
        "routes": routes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--list-public", action="store_true")
    args = parser.parse_args()

    report = audit()
    if args.json:
        print(json.dumps(
            {k: v for k, v in report.items() if k != "routes"},
            indent=2, sort_keys=True, default=str,
        ))
        return 0 if not report["undeclared_public"] and not report["admin_path_not_admin_gated"] else 1

    print(f"routes enumerated      : {report['total_routes']}")
    print(f"  authenticated        : {report['authenticated']}")
    print(f"  admin-gated          : {report['admin_only']}")
    print(f"  public               : {report['public']} "
          f"({report['declared_public']} declared, "
          f"{len(report['undeclared_public'])} UNDECLARED)")

    if args.list_public:
        print("\nall public routes:")
        for r in sorted(report["routes"], key=lambda x: x["key"]):
            if not r["authenticated"]:
                mark = " " if r["key"] in PUBLIC_ROUTES else "!"
                print(f"  {mark} {r['key']:58s} {r['file']}:{r['line']}")

    if report["admin_path_not_admin_gated"]:
        print(f"\nADMIN-PATH ROUTES WITHOUT AN ADMIN DEPENDENCY "
              f"({len(report['admin_path_not_admin_gated'])}):")
        for r in report["admin_path_not_admin_gated"]:
            print(f"  {r['key']:58s} {r['file']}:{r['line']}  deps={r['dependencies'] or 'NONE'}")

    if report["undeclared_public"]:
        print(f"\nUNDECLARED PUBLIC ROUTES ({len(report['undeclared_public'])}):")
        for r in sorted(report["undeclared_public"], key=lambda x: x["key"]):
            print(f"  {r['key']:58s} {r['file']}:{r['line']}")
        print("\nEach must either take an auth dependency or be added to "
              "PUBLIC_ROUTES with a reason.")

    ok = not report["undeclared_public"] and not report["admin_path_not_admin_gated"]
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
