# Security policy

## Supported release

Only the latest `2.x` release receives security fixes.

## HTTP deployment boundary

The application speaks HTTP by design. HTTP provides neither confidentiality
nor transport integrity. For any untrusted network, operators must terminate
TLS at a reverse proxy/router or use a trusted VPN. The backend listener should
be restricted to the proxy address or localhost whenever possible.

API keys are bearer credentials. Anyone who observes one can use it until it is
revoked. Never place keys in URLs, repository files, Compose environment
variables, logs, chat messages, or public CI output.

## Operator checklist

- Generate, list and revoke keys only with `api_keys.py` on the server.
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
