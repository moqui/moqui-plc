# Project conversation and decision history

This is the portable project transcript distilled from the complete working
conversation. It preserves every architectural requirement, explicit decision,
scope boundary, implementation request, and test decision needed to resume the
work. It intentionally excludes platform-internal prompts and tool metadata.

## 1. Architecture introduced by the developer

- `moqui-framework` master is the central platform. `moqui-math` and
  `moqui-device` are Moqui runtime components that materialize their entity and
  service models during `gradlew load`.
- With those models and other components, Moqui acts as SCADA/MES/DCS for many
  factory PLCs. Moqui Screens replace traditional HMIs.
- `moqui-device-gateway` is the edge gateway. It moves data asynchronously
  between Moqui and PLCs without loading the Moqui runtime with protocol work.
  The gateway model and requests are entirely based on `moqui-device`.
- Moqui activates the gateway through the services in
  `DeviceGatewayServices.xml`. Integrations share the
  `service type="interface"` / `run#DeviceRequest` pattern. `moqui-plc4j` and
  `moqui-genicam` are symmetric examples.
- `moqui-plc` is a deterministic PLC framework. CODESYS IEC 61131-3 is the
  primary implementation, with scripts projecting it to Simatic AX and MISRA C
  IoT firmware.
- The intended link is OPC UA or MQTT v5 through Artemis in
  `moqui-deploy/industrial`.

## 2. Agentic low-code/no-code objective

- Improve `moqui-plc/agent-skills` so an agent can guide a PLC developer through
  machine decomposition, systems/subsystems, leaf devices, device
  classification, signals, parameters, naming rules, EPLAN/CSV/datasheet
  imports, FSM topology, review and approval.
- Generate Moqui seed data for Device, PhysicalDevice, DeviceGroup,
  DeviceGroupMember, Parameter, DeviceConfig, DeviceRuleSet/DeviceRule,
  DeviceRequest and DeviceRequestItem.
- Populate StatusFlow entities for UI-visible machine/system state.
- Generate or assist PLC code faithfully from the `mantle-hvac` and test-suite
  templates, following `MoquiStart`, configuration management, `Main`,
  `MainRuleEngine`, facades, manager, diagnostics, and signal-update code.
- The workflow should be usable from VS Code by loading agent skills or later
  through `moqui-mcp`.

## 3. Broader Moqui platform context

- The gateway database is always a Moqui database, normally PostgreSQL or
  YugabyteDB, even if the Moqui runtime is hidden.
- Moqui plus components such as `moqui-jep` and `moqui-mcp` is also a platform
  for agentic applications, not only business applications.
- Seed/project patterns should reuse examples from `moqui-mcp`, cybersecurity,
  UL508A/electrical compliance, GenICam, HiveMind and PLM/Graph population.
- A generated engineering project may be represented as a HiveMind WorkEffort
  project with milestones such as electrical bill/schematic collection, wiring
  verification, device tree, vendor drive/servo/network setup, process
  validation, FAT/SAT, timing and diagnostics, with external safety explicitly
  identified.
- Project specifications may optionally be archived in Moqui Wiki entities and
  linked to the HiveMind WorkEffort through `WikiPageWorkEffort`. Chat/session
  persistence remains the responsibility of the chat host, but the project
  workflow must also have portable on-disk state.

## 4. StatusFlow and PLC-code authority

- Upstream PR `moqui/moqui-framework#720` adds transitions to sub-StatusFlows
  and a StatusFlow stack.
- Do not modify/redesign StatusFlow entities. The tool is not responsible for
  nonsensical developer FSM choices.
- `StatusFlowStack` may evolve into both an append-oriented state log and a
  push-down automaton memory, analogous to `ParameterLog`; `thruDate` does not
  make sense for that role.
- StatusFlow in the database is authoritative for states and transition
  topology used by UI/search.
- Executable predicates, numerical-to-boolean interpretations, state output
  functions, interlocks, FSM stitching and invocation order belong directly in
  PLC code, assisted and validated by the agent. They should not be forced into
  the database.
- FSMs are often flat and independently assigned to systems/subsystems. Nested
  FSMs are optional, not mandatory. Subsystem FSMs in one Application execute
  sequentially in the developer-approved priority order.

## 5. Controller/Application model

- A CODESYS Project may contain multiple CODESYS Application objects.
- Every CODESYS Application has a dedicated copy of the moqui-plc framework,
  runtime component, task configuration and device tree.
- Each hardware PLC CPU is analogous to one CODESYS Application and is modeled
  as a distinct Device/PhysicalDevice.
- Multiple top-level systems managed by one Project may therefore live in
  separate Applications.
- Physical binding, CODESYS device tree construction, vendor configuration and
  merges remain manual developer work.

## 6. Device/control semantics and safety boundary

- Functional safety is outside the framework. It belongs to drives with STO,
  safety relays and safety PLCs. The standard PLC may observe boolean
  stop/fault signals.
- `Actuator` separates a logical Req/Ack control plane
  (`enableRequest`/`disableRequest`, VAR_IN_OUT) from the physical data plane
  (`enable`/`disable`, feedback sensors, fault and reference/feedback data).
- The same Actuator abstraction covers contactor-driven motors and intelligent
  drives. Control/status words can be mapped to Actuator; internal drive PID or
  safety remains outside moqui-plc.
- Atomic delivery responsibility ends at the configured MQTT v5/OPC UA
  boundary. Do not recreate an acknowledgement protocol above MQTT. Broker
  persistence and delivery policy are the applicable guarantee.

## 7. Explicit scope decisions

- Physical binding stays manual.
- Test suites are generated only when requested.
- Semantic validation of developer expressions is outside automatic
  responsibility; the developer may discuss/review them with the agent.
- DeviceGroup modeling and membership are explicitly supplied by the developer;
  the agent materializes approved seed data and does not infer redundancy.
- Redundancy mechanisms are excluded; only data modeling may describe the
  chosen topology.
- Simatic AX and IoT firmware projections use existing Python scripts.
- Obsolete `DeviceConfigSet` and `DeviceConfigSetMember` must never be used.

## 8. Configuration and live-parameter decisions

- Recipes contain configurable values, excluding actual durations and measured
  feedback/runtime state.
- `MqttParameterSub` must be generated per Application from a developer-approved
  subset of already modeled Parameters.
- For the official base HVAC demo, live parameters are:
  `tempSetpoint`, `tempHysteresis`, `tempMin`, `tempMax`, `rhSetpoint`,
  `rhHysteresis`, `rhMin`, `rhMax`, `ductTempMin`, `ductTempMax`, `ductRhMax`,
  `setPointTimeHigh`, `setPointTimeLow`, `processEstimatedDuration`,
  `processMinDuration`, `processRemainingDuration`, `estimatedRuntime`,
  `minRuntime`, `estimatedBreakDuration`, and `minBreakDuration`.
- The standard outbound `ParametersToJsonMapper` was updated in IEC and IoT
  firmware for those 20 fields. Simatic AX was not changed because MQTT is not
  supported there.
- The generic executable inbound example was removed. `JsonToParametersMapper`
  is documentation/no-op until an Application-specific whitelist mapper is
  generated.
- Device and parameter logical names must never have a `dev.` prefix in Moqui.
  The PLC/recipe projection adds IEC access syntax.

## 9. Documentation and implementation already completed

- The `moqui-device` README was expanded to explain continuous trajectories vs
  discrete-event systems and the HVAC seed-first workflow.
- Official HVAC seed data was added as `moqui-device/data/HVACDemoData.xml`.
- Session/bootstrap architectural context was added to the agent skills so new
  agents do not start from an empty context.
- The gateway recipe projection was corrected to add logical PLC paths at the
  projection boundary.
- Standard live-parameter mappings and CODESYS projectarchive updates were
  committed without AI references using the `moqui-industrial` identity.

## 10. Commit history supplied during the work

- `moqui-device`:
  - `63c2e4e feat(data): add mantle HVAC demo model`
  - `93103e5 docs: clarify trajectory and DES semantics`
  - `158b2d0 docs: describe HVAC seed-first workflow`
- `moqui-device-gateway`:
  - `a9d56e5 fix(recipe): project logical names to PLC paths`
- `moqui-plc`:
  - `5ba0232 feat(agent-skills): bootstrap industrial project context`
  - `29cbacb feat(hvac): publish standard live parameters`
  - `1fb5cd8 chore(codesys): update HVAC parameter mappers`
- Commit identity requirement:
  `moqui-industrial <729502+moqui-industrial@users.noreply.github.com>`.
  Commit messages must be technical and must contain no AI references.

## 11. Defrost proposal and cancellation

- A temporary HVAC E2E extension was proposed with an electric defrost
  resistance and defrost/dripping durations.
- The developer then explicitly said not to implement it and to avoid it.
- No defrost/dripping implementation was committed. The active test uses only
  the official base HVAC seed and standard parameters.

## 12. Current E2E test conversation

- The developer requested a three-component application test with moqui-plc,
  moqui-device-gateway and Artemis, using Mosquitto to observe MQTT. PostgreSQL
  remains the hidden persistence dependency of the gateway.
- CODESYS tasks/program calls planned: `MoquiStart`, `LogDispatcher`,
  `MqttParameterSub`; `MqttParameterPub` is needed later for outbound parameter
  publication.
- Docker Desktop was started.
- Artemis initially failed because Windows checked out `artemis-start.sh` and
  `broker.xml` with CRLF. They were normalized locally to LF without commit.
- Artemis primary and backup then started and synchronized successfully.
- PostgreSQL was started from the industrial deployment. Moqui required the
  official `getPostgresJdbc` task and load order `seed-initial` followed by
  `seed`.
- The database was verified to contain 16 HVAC devices, 33 HVAC parameters,
  the live request and 20 request items.
- Gateway dynamic MQTT endpoints did not inject configured credentials into a
  seed `brokerUri`; temporary database-only credentials were added for the
  test. `onlyChangedParameters` was temporarily set to `N` to force the initial
  send without synthesizing EntityAuditLog changes.
- All 20 messages were published and observed. The local callback to Moqui on
  port 8080 caused a post-publication REST 500, so the gateway was restarted
  with `mqtt.write.afterPublish.enabled=false`; REST then returned completed.
- A security issue was observed: REST `publishUriList` exposed the MQTT password
  even though Camel logs masked it.
- The developer asked whether IDE simulation was sufficient. The accepted test
  target is CODESYS Control Win x64; CODESYS Gateway connects the IDE to the
  runtime but is not part of MQTT transport.
- The final screenshot showed `RUN` together with the red `SIMULAT` indicator,
  and only a test task visible. No CODESYS process had an established connection
  to port 1883. The immediate action is documented in `resume-summary.md`.

## 13. E2E execution and mapper-direction correction

- CODESYS Control Win was run outside simulation and established an MQTT
  connection to Artemis on `127.0.0.1:1883`.
- Gateway execution of `HVAC_DEMO_LiveParametersWrite` completed with 20 rows.
  CODESYS received the payloads, deserialized them and invoked
  `JsonToParametersMapper` with keys including `tempSetpoint` and
  `minBreakDuration`.
- The earlier mapper decision was corrected: the 20 approved live-write fields
  belong in executable `JsonToParametersMapper`, not in the outbound
  `ParametersToJsonMapper`. Mapper names remain unchanged because they already
  describe their directions correctly.
- IEC and both IoT firmware source trees now implement exactly the 20
  DeviceRequestItem names. The outbound mapper has returned to runtime
  telemetry. The CODESYS projectarchive still requires the developer's update
  and a final live-value write test before commit.
- The outbound decision was then tightened: `ParametersToJsonMapper` remains a
  documentation-only example unless a project explicitly requests parameter
  replication between PLCs/Applications for redundancy. `MqttParameterPub` is
  disabled by default and is not a telemetry path. `LogDispatcher` owns numeric
  and textual telemetry; actuator, PID and log serializers remain separate and
  executable.
- `LogDispatcher` reached the gateway over MQTT, but DeviceLog persistence
  failed because the payload source did not resolve to a valid Device.

## 14. DeviceLog and ParameterLog identity contract

- The PLC `LogEvent` structure remains unchanged. `loggerName` is interpreted
  as the exact `Device.deviceId`, not as a display name or diagnostic category.
- An empty `source` identifies a device-scoped event. A non-empty `source` is
  the exact pre-existing `Parameter.parameterId` and identifies a
  parameter-scoped event. Numeric/text/enum payload types are independent of
  this scope.
- The gateway now routes these two cases directly and never builds a parameter
  ID by concatenating `loggerName` and `source` or creates an unknown parameter.
- HVAC application/framework loggers use `HVAC_DEMO_PLC`; actuator, group and
  PID loggers use their exact configured device IDs. The periodic HVAC
  `ParameterLogger` uses exact parameter IDs and a one-minute PLC clock pulse.
- The focused gateway integration test passed all DeviceLog and ParameterLog
  scenarios. The PLC regression suite passed 23 tests. Final CODESYS archive
  import, compilation, and live observation remain pending; no commit was made.

## 15. Manual platform projection

- The developer explicitly requested file-by-file changes in Simatic AX and
  IoT firmware without running regeneration scripts.
- Simatic AX was aligned with exact device/parameter IDs, received a native
  HVAC `ParameterLogger`, and compiled successfully for S7 and LLVM.
- Both IoT source trees were aligned. Device events now carry empty `source`;
  numeric parameter events carry exact `Parameter.parameterId`. The ring buffer
  preserves all 29 values across multiple MQTT batches.
- Changed IoT C sources passed local C11 syntax checks. The full ESP-IDF Docker
  build remains pending because downloading the missing toolchain image timed
  out without reaching compilation.
