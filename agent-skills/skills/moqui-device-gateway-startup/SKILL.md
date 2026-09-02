---
name: moqui-device-gateway-startup
description: Use when the user wants a guided first startup of moqui-device-gateway from reviewed Moqui seed data. This skill inspects the modeled gateway identity, device groups, and DeviceRequest rows, then emits a step-by-step startup checklist aligned with the gateway README and automated tests.
license: ../../LICENSE.md
compatibility: Requires Python 3.14+
metadata:
  author: moqui-industrial
  version: "1.0"
---

# Moqui Device Gateway Startup

Use this skill when the user asks to prepare or guide the first startup of
`moqui-device-gateway` for a modeled PLC/gateway application.

## Goal

Keep gateway startup model-driven and data-driven:

- the reviewed Moqui seed remains the source of truth
- gateway identity comes from modeled `Device` / `PhysicalDevice`
- startup scope comes from `DeviceGroup` / `DeviceGroupMember`
- runtime routes come from active `DeviceRequest` rows
- MQTT live-parameter and PLC-log behavior stays aligned with the modeled
  request catalog

## Workflow

1. Read the reviewed seed XML or the saved session workspace.
2. Identify:
   - gateway candidates from `DeviceGroupMember.purposeEnumId = DgmpEdgeGateway`
   - in-scope PLC/controller devices in the same groups
   - active `DeviceRequest` rows routed through `DrrMoquiDeviceGateway`
3. Check for structural gaps that would block first startup:
   - missing gateway identity
   - missing gateway group membership
   - gateway without any in-scope PLC/controller
   - routed requests that are not reachable from the gateway scope
4. Generate a step-by-step startup guide with concrete IDs and commands.
5. Keep the generated guide in the session workspace when a session is used.

## Required Behavior

- prefer the reviewed seed saved in the session over ad-hoc notes
- do not invent gateway IDs or request names not present in the model
- report missing model data as startup blockers, not as optional warnings
- keep the guide aligned with the real `moqui-device-gateway` README and test
  expectations
- treat the gateway startup guide as a projection of the modeled data, not as a
  parallel manual configuration source

## Helper Script

- `scripts/render_gateway_startup_guide.py`
  - reads `--seed` or `--session-dir`
  - generates a Markdown first-startup checklist
  - writes by default into `generated-config/gateway-startup-guide.md` when a
    session is used
  - highlights blockers if the model is not sufficient for startup

## References

- `references/first-startup-workflow.md`
- `references/model-preflight-rules.md`
- `scripts/README.txt`
