# Security policy

## Supported release

Only the latest `3.x` release receives security fixes.

## HTTP deployment boundary

The application speaks HTTP by design. HTTP provides neither confidentiality
nor transport integrity. For any untrusted network, operators must terminate
TLS at a reverse proxy/router or use a trusted VPN. The backend listener should
be restricted to the proxy address or localhost whenever possible.

API keys are bearer credentials. Anyone who observes one can use it until it is
revoked. Never place keys in URLs, repository files, Compose environment
variables, logs, chat messages, or public CI output.

The public `/` page and `/admin` never persist an entered key in browser
storage. They hold it in page memory and send it as an Authorization header to
same-origin APIs. Guests can only follow external mirrors; local artifacts
require a `user` or `admin` key. Browser downloads use a 60-second single-use
ticket whose plaintext is not stored by the server.

Because the transport is HTTP, these controls do not protect a key or ticket
from network observation. The deployment boundary remains responsible for
transport protection.

## Operator checklist

- Bootstrap the first admin key with `api_keys.py` on the server; create later
  keys only through that CLI or the authenticated admin interface.
- Use `user` keys for consumers; reserve `admin` for operators and publishers.
- Keep at least two separately labelled administrator keys during rotation.
- Revoke replaced or suspected keys immediately.
- Restrict access to `.env` and the complete `var/` tree.
- Back up the complete `var/` tree together and test restores.
- Keep Docker Desktop, the host OS and the container image updated.
- Retain and monitor container audit logs for authentication failures, rate
  limits and unexpected write requests.
- Do not publish port 8080/8081 directly to the Internet without a protected
  routing boundary.

## Reporting

Report suspected vulnerabilities privately to the repository owners. Do not
include API keys, private dataset metadata, or artifact contents in an issue.
