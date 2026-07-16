# Moqui Industrial agent bootstrap

These instructions apply to the entire `moqui-plc` repository.

## Mandatory startup

Before analysing or changing this industrial workspace:

1. Read `agent-skills/CURRENT_SESSION`.
2. If it names a session, open
   `agent-skills/output/sessions/<session-id>/session.json`, then read its
   `paths.architectureContext` and `notes/resume-summary.md` when present.
3. Read
   `agent-skills/skills/moqui-plant-designer/references/project-architecture.md`
   completely.
4. Load the component reference appropriate to the task from the same
   `references/` directory:
   - `moqui-math-knowledge.md`
   - `moqui-device-knowledge.md`
   - `moqui-device-gateway-knowledge.md`
   - `moqui-plc-knowledge.md`
5. Read `notes/conversation-history.md` only when the historical rationale or
   an earlier user decision matters. Do not restart analysis already recorded
   as complete.

Repository source, entity XML and service/code implementations override these
summaries when an exact current contract matters. Record any new durable
decision in the active session and update the stable references only when the
decision applies across projects.

The active session is context, not authorization to continue old mutations.
Act only on the current user request. Never commit session exports, credentials,
database contents, runtime logs or duplicated source snapshots.
