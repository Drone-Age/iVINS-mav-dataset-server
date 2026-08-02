# Component release checklist

- Commit SHA:
- Backend:
- Frontend:
- Process:
- Compatibility manifest reviewed:

## Before release

- [ ] Change request approved
- [ ] Acceptance criteria met
- [ ] Component changelogs updated
- [ ] Unit/integration/security tests passed
- [ ] Compose configuration validated
- [ ] Production image built
- [ ] Critical/High vulnerability gate passed or exception approved
- [ ] Backup and rollback reference recorded
- [ ] Working tree clean

## Publish

- [ ] Backend component tag/release created if changed
- [ ] Frontend component tag/release created if changed
- [ ] Process component tag/release created if changed
- [ ] Releases point to the reviewed commit

## Deploy and verify

- [ ] `/health` and `/versions` match the manifest
- [ ] Public catalog smoke test passed
- [ ] User/Admin authorization smoke test passed
- [ ] BAG storage/integrity smoke test passed
- [ ] Restart policy verified
- [ ] Result recorded; rollback or incident opened on failure
