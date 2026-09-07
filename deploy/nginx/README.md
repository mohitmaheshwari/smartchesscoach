# Production nginx config (chessguru.ai)

These are the **live** configs from the production host (72.60.204.176),
captured 2026-09-07. They were previously untracked, so the entire TLS and
security-header posture existed only on that one machine and would have been
lost on any reprovision.

`docker/nginx.conf` in this repo does **not** serve chessguru.ai. A host
nginx (Ubuntu package) does. Edit the files here, then apply them.

| File | Deploys to |
|---|---|
| `chessguru.ai.conf` | `/etc/nginx/sites-available/chessguru.ai` (symlinked into `sites-enabled/`) |
| `chessguru-security-headers.conf` | `/etc/nginx/snippets/chessguru-security-headers.conf` |

Also set globally in `/etc/nginx/nginx.conf` (not tracked here because it is
shared with other products on the same host):

    server_tokens off;

## Applying a change

    scp deploy/nginx/chessguru.ai.conf root@72.60.204.176:/etc/nginx/sites-available/chessguru.ai
    scp deploy/nginx/chessguru-security-headers.conf root@72.60.204.176:/etc/nginx/snippets/
    ssh root@72.60.204.176 'nginx -t && systemctl reload nginx'

Never `systemctl restart` — `reload` keeps connections alive and, if the new
config is bad, `nginx -t` fails first and the old config keeps serving.

## The add_header trap

nginx drops **every inherited `add_header`** in a location block that
declares its own. The static-asset location sets `Cache-Control`, so without
including the security-headers snippet a second time inside it, every `.js`
and `.css` would ship with no security headers at all. Both include sites are
required. Verify after any change:

    curl -sI https://chessguru.ai/static/js/main.<hash>.js | grep -i strict-transport

## CSP is Report-Only on purpose

An enforcing policy needs an audit of the app's real resource origins (the
Stockfish wasm workers especially) or it white-screens the product. Promote
`Content-Security-Policy-Report-Only` to `Content-Security-Policy` only after
confirming no violations in a real session.
