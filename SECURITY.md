# Security policy

[Українська версія](SECURITY.uk.md)

## Supported release

Only the latest `4.x` release receives security fixes.

## TLS deployment boundary

The application speaks HTTP only inside the private Compose network. The Docker
release exposes pinned Caddy on 80/443, redirects HTTP to HTTPS, obtains and
renews the certificate automatically, and sends HSTS. Gunicorn has no host
port. A valid public certificate still requires correct DNS and outbound ACME
access.

API keys are bearer credentials. Anyone who observes one can use it until it is
revoked. Never place keys in URLs, repository files, Compose environment
variables, logs, chat messages, or public CI output.

The public `/` page and `/admin` never persist an entered key in browser
storage. They hold it in page memory and send it as an Authorization header to
same-origin APIs. Guests can only follow external mirrors; local artifacts
require a `user` or `admin` key. Browser downloads use a 60-second single-use
ticket whose plaintext is not stored by the server.

Caddy access logging is disabled so credentials, ticket query values and
private artifact paths cannot enter the proxy journal. Operators must run
`verify-tls.ps1` before provisioning the e2e key or allowing public clients.

## Operator checklist

- Bootstrap the first admin key with `api_keys.py` on the server; create later
  keys only through that CLI or the authenticated admin interface.
- Use `user` keys for consumers; reserve `admin` for operators and publishers.
- Store the dedicated e2e user key only as `DSM_SERVER_TOKEN`; never put it in
  Compose, Git, logs, evidence or command histories.
- Keep at least two separately labelled administrator keys during rotation.
- Revoke replaced or suspected keys immediately.
- Restrict access to `.env` and the complete `var/` tree.
- Back up the complete `var/` tree together and test restores.
- Keep Docker Desktop, the host OS and the container image updated.
- Retain and monitor container audit logs for authentication failures, rate
  limits and unexpected write requests.
- After TLS verification, revoke any key that may have traversed the old HTTP
  endpoint and confirm the replacement key succeeds only through HTTPS.
- Do not add a host port for the Backend service.

## Reporting

Report suspected vulnerabilities privately to the repository owners. Do not
include API keys, private dataset metadata, or artifact contents in an issue.
