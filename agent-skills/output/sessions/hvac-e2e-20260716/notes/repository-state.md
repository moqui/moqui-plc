# Repository state at session capture

Captured on 2026-07-16. Re-run `git status`, `git branch --show-current`,
`git log` and inspect current files after cloning on another computer.

## moqui-plc

- Branch: `master`
- Remote: `https://github.com/moqui/moqui-plc.git`
- HEAD: `1fb5cd8 chore(codesys): update HVAC parameter mappers`
- Earlier relevant commits:
  - `29cbacb feat(hvac): publish standard live parameters`
  - `5ba0232 feat(agent-skills): bootstrap industrial project context`
- Dirty state at capture: only this untracked session directory.

## moqui-device

- Branch: `main`
- Remote: `https://github.com/moqui/moqui-device.git`
- HEAD: `158b2d0 docs: describe HVAC seed-first workflow`
- Earlier relevant commits:
  - `93103e5 docs: clarify trajectory and DES semantics`
  - `63c2e4e feat(data): add mantle HVAC demo model`
- Clean at capture.

## moqui-device-gateway

- Branch: `main`
- Remote: `https://github.com/moqui/moqui-device-gateway.git`
- HEAD: `a9d56e5 fix(recipe): project logical names to PLC paths`
- Clean at capture.

## moqui-deploy

- Branch: `master`
- Remote: `https://github.com/moqui/moqui-deploy.git`
- HEAD: `2af73f8 Merge pull request #1 from moqui-industrial/feat/industrial-profile`
- Deliberately dirty test state:
  - `industrial/activemq/artemis-start.sh` converted CRLF -> LF locally;
  - `industrial/activemq/broker.xml` converted CRLF -> LF locally;
  - `industrial/db/` is untracked PostgreSQL test data.
- Do not commit the database directory or assume it is portable. Restore the DB
  from seed data on a new computer.

## moqui-framework

- Branch: `feat/statusflow-hsm`
- Industrial remote:
  `https://github.com/moqui-industrial/moqui-framework.git`
- Upstream remote: `https://github.com/moqui/moqui-framework.git`
- HEAD: `82813476 feat(entity): make StatusFlowStack append-only`
- Previous HSM/PR720-related commit:
  `87afc9d6 Extend StatusFlow for hierarchical FSM; add physics and engineering UoMs`
- Clean tracked state at capture. The PostgreSQL JDBC driver downloaded into
  runtime may be ignored and must be recreated with `gradlew getPostgresJdbc`
  on a fresh checkout.

## Commit identity and policy

If future approved work is committed/pushed, use:

```text
moqui-industrial <729502+moqui-industrial@users.noreply.github.com>
```

Use technical messages only. Do not include AI references. This E2E demo and
session capture were explicitly kept uncommitted at the time of capture.
