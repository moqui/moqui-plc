# Moqui Industrial project architecture

Read this reference before starting or resuming any plant-design session. It is
the stable architectural context shared by all projects; project-specific facts
belong in the saved session surveys and seed XML.

## Mandatory source verification

Do not rely on this summary when an exact field, service contract or code
signature matters. At the beginning of a new implementation, inspect the
current checkout in this order:

1. `moqui-math/README.md`, `moqui-math/entity/MathEntities.xml`,
   `moqui-device/README.md`, `moqui-device/entity/DeviceEntities.xml` and
   `DeviceViewEntities.xml`.
2. `moqui-device/service/moqui/device/DeviceGatewayServices.xml` and
   `DeviceServices.xml`, then `moqui-device-gateway/README.md`, routes and SQL.
3. `moqui-plc/README.md`; follow the CODESYS call chain from `MoquiStart.st`
   through device configuration, `Main`, `MainRuleEngine`, `DeviceFacade`,
   `IOFacade`, `DeviceManager`, diagnostics and signal update functions.
4. Read the complete `mantle-hvac` component and relevant axis/group test suites
   before generating PLC code. Treat these as executable templates.
5. Inspect `moqui-framework` BasicEntities StatusFlow definitions, including the
   sub-flow/stack changes corresponding to upstream PR 720, without redesigning
   StatusFlow itself.
6. Use `docs/ASDP-M-*.pdf` as the system-engineering/FSM/device theory source.
7. For seed/project patterns, inspect HiveMind project data plus the PLM and
   Graph seed examples in `moqui-cybersecurity-agent` and
   `moqui-electrical-compliance-agent`; do not recreate patterns already there.
8. For deployment facts, inspect `moqui-deploy/industrial`, including Artemis,
   MQTT, PostgreSQL/YugabyteDB and OpenSearch configuration.

Entity XML and service/code implementations override prose if the checkout has
evolved. Record any project-specific interpretation in the saved session.

## Platform layers

- `moqui-framework` is both the business-application runtime and the platform
  for agentic applications. `moqui-math` and `moqui-device` are runtime
  components whose entities and services materialize the industrial model.
- The Moqui database (normally PostgreSQL or YugabyteDB in production) remains
  the authoritative database used by `moqui-device-gateway`, even when the
  Moqui runtime is hidden behind services.
- DataDocuments/DataFeeds may denormalize authoritative entities into
  OpenSearch for search or embeddings. They are projections, never a second
  source of truth.
- `moqui-device-gateway` isolates asynchronous PLC traffic from the Moqui
  runtime. Field-side requests use MQTT v5 or OPC UA; Moqui-side wrapper
  requests call the gateway through REST callbacks.
- Device integrations follow the `run#DeviceRequest` service-interface pattern.
  `moqui-plc4j` and `moqui-genicam` are symmetric protocol implementations;
  PLC4J peer-to-peer fieldbus communication is optional, not the primary path.
- `moqui-plc` is the deterministic control framework. Its CODESYS IEC 61131-3
  implementation is the primary template; existing scripts project it to
  Simatic AX and MISRA C IoT firmware.

## Responsibility boundary

- Moqui may approve and publish setpoints, parameters and trajectories.
- Delivery responsibility ends at the configured MQTT v5 or OPC UA boundary.
  Do not invent another acknowledgement protocol above the existing transport.
- MQTT uses broker persistence and an explicit delivery policy. PLC runtime or
  hardware failures after delivery remain outside Moqui's responsibility.
- Functional safety is outside this framework. Safety drives, STO modules,
  safety relays and safety PLCs own safety behavior. The standard PLC may only
  observe boolean stop/fault signals.
- Physical binding, wiring verification, CODESYS device trees, vendor-specific
  drive/network configuration, task configuration, source merges and
  redundancy mechanisms remain developer-owned.

## Application and controller model

- One hardware CPU or one CODESYS `Application` is one distinct
  `Device`/`PhysicalDevice`.
- A CODESYS Project may contain multiple Applications. Each Application has its
  own copy of the moqui-plc framework, runtime component, tasks and device tree.
- Multiple subsystem FSMs inside one Application execute sequentially in the
  unique developer-approved invocation priority. Their coordination is code,
  not an inferred database relationship.
- DeviceGroups and memberships are explicitly supplied and approved by the PLC
  developer. The agent validates and materializes them but does not infer them.

## Naming boundary

- Moqui stores domain identity, not IEC access syntax.
- `PhysicalDevice.deviceName` is a logical instance name such as
  `coldGlycolPump`; never store `dev.coldGlycolPump`.
- `ParameterDef.parameterName` and `Parameter.parameterAlias` are logical field
  names such as `tempSetpoint` or `enableTime`; never store a leading `dev.`.
  Device ownership already supplies the device namespace.
- The PLC generator and recipe-export projection add the global `dev.` namespace
  when producing IEC code or CODESYS txtrecipe lines. MQTT JSON keys remain the
  explicitly reviewed `DeviceRequestItem.requestItemName` values.

## Authoritative model and generated code

- Seed XML is authoritative for devices, physical devices, groups, parameters,
  configurations, requests, StatusFlow states and transition topology.
- `StatusFlow` represents UI-visible orchestration topology. Prefer independent
  flat flows assigned to systems/subsystems; use nested flows only when the
  developer explicitly requires push-down behavior.
- Do not modify `StatusFlow` entities to compensate for poor application
  semantics. `StatusFlowStack` may evolve into an append-oriented state log and
  push-down memory, analogous to `ParameterLog`; `thruDate` is not meaningful
  for that role.
- PLC code is authoritative for boolean predicates, numerical-to-boolean
  interpretation, state output functions, interlocks, FSM stitching and call
  order. Do not try to persist those executable semantics in Moqui.
- The agent assists the developer in writing and validating code faithfully
  from `mantle-hvac` and existing test-suite patterns; it does not replace the
  developer or accept responsibility for process semantics.

## Device and configuration semantics

- `Actuator` separates a logical Req/Ack control plane
  (`enableRequest`/`disableRequest`, normally `VAR_IN_OUT`) from the physical
  data plane (`enable`/`disable`, enabled/disabled sensors, fault and reference/
  feedback values).
- Actuator polymorphism covers bistable devices, contactor-driven motors and
  intelligent drives. Drive control/status words may map into Actuator signals;
  drive-internal control and safety remain inside the drive.
- `DeviceConfig` is an atomic type-level reusable configuration.
  `DeviceRule` binds it to one compatible device instance.
  `DeviceRuleSet` is the ordered multi-device recipe composition boundary.
- Recipes contain configurable values only. Exclude actual durations, measured
  feedback and other runtime state.
- MQTT live updates are a developer-approved whitelist over existing
  device-bound Parameters. Generate an Application-specific mapper; never copy
  an example mapper blindly.

## Agent workflow and persistence

1. Capture project scope and decompose machine, systems and subsystems.
2. Classify leaf devices and their logical control/feedback patterns.
3. Import and review schematics, EPLAN/CSV bills, datasheets and naming rules.
4. Capture signals, sampling domains, controller/Application topology, explicit
   DeviceGroups and transport architecture.
5. Collect UI-visible FSM topology, then code-owned predicates and output
   policies with separate approval gates.
6. Generate and review Moqui seed XML, recipes/live whitelist, PLC code and
   gateway configuration.
7. Leave FAT/SAT, timing/diagnostic verification and physical commissioning to
   the developer workflow; generate test suites only when requested.

Persist every project in a session directory. The chat provider may preserve
conversation history, but agents must be able to resume from `session.json`,
survey answers, attachments, reviewed seed and a snapshot of this architecture
reference. On explicit request, archive specifications in Moqui Wiki entities
and link them to the HiveMind WorkEffort through `WikiPageWorkEffort`.
