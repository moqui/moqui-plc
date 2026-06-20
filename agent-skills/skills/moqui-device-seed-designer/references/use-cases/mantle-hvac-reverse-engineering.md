# Mantle HVAC Reverse Engineering

This case study shows how an existing `moqui-plc` HVAC application can be
decomposed into Moqui seed data structures for use with the seed-first skill
workflow.

## Reverse-engineering target

The goal is to identify:

- one root machine/controller device
- the atomic physical devices used by the PLC logic
- the logical device groups representing subsystems
- the first shared parameter catalog (`ParameterDef`)
- the first parameter instances (`Parameter`)
- the standard request layer
- the first `DeviceConfig` template and rule layer

## Mantle HVAC decomposition

### Root device

One root controller device could represent the overall HVAC machine or cell.

Example:

- `HVAC_CELL_01`

### Atomic child devices

In a seed-first model, each atomic PLC FB should correspond to a `Device` plus
`PhysicalDevice`.

Typical `mantle-hvac` examples:

- `coldGlycolPump`
- `coldGlycolValve`
- `hotGlycolPump`
- `hotGlycolValve`
- `ahuFan`
- `airFlow`

Depending on the PLC abstraction, these may map to:

- `Actuator`
- `ProcessPid`
- `DtInputAnalogSensor`
- `DtInputDigitalSensor`
- `DtOutputDigitalSensor`

## Device groups as subsystems

The seed model should represent subsystem decomposition explicitly using
`DeviceGroup` and `DeviceGroupMember`.

Examples:

- `ColdGroup`
  - `coldGlycolPump`
  - `coldGlycolValve`
- `HotGroup`
  - `hotGlycolPump`
  - `hotGlycolValve`

These groups are useful because the PLC logic often controls them as one
logical unit through group-level enable/disable requests.

## ParameterDef reuse

The key modelling principle is reuse of `ParameterDef`.

For all devices of the same `deviceTypeEnumId`:

- the same `ParameterDef` rows should normally be reused
- each concrete `Device` gets its own `Parameter` rows
- each `DeviceConfig` for the same `deviceTypeEnumId` reuses the same
  `ParameterDef` records, but normally only for the configurable subset

This gives the biggest long-term payoff in maintainability.

## Standard request layer

For a `moqui-plc` based machine, the request layer should usually stay small:

1. framework `ec` read/write request
2. recipe export request
3. one live MQTT-parameter request

The modelling effort should stay focused on:

- devices
- groups
- parameters
- status flows
- configs and rules

## DeviceConfig and rules

Once the base device tree and parameter catalog are defined, a first
`DeviceConfig` template can be generated for each relevant device type.

For `mantle-hvac`, this means:

- first define the root device and atomic devices
- then define subsystem groups
- then derive the first `DeviceConfig TEMPLATE`
- finally create `DeviceRuleSet` and `DeviceRule` rows only where needed

## Why keep this file

This document is useful as a real use case because it shows how to move from:

- existing PLC code

to:

- Moqui seed data
- digital twin structures
- downstream PLC/code/config generation
