# DeviceConfig Load Workflow

This reference makes the recipe-loading workflow explicit inside
`moqui-device-seed-designer`.

## Core distinction

- `DeviceConfig`
  - reusable configuration template for one `deviceTypeEnumId`
- `DeviceConfigSet`
  - reusable configuration set for one `DeviceGroup`
- `DeviceConfigSetMember`
  - membership rows that compose the set
- `DeviceRuleSet`
  - ordered sequence of `DeviceRule`
- `DeviceRule`
  - instance-level binding between one config and one specific logical `Device`

## Compatibility rule

`DeviceRule.deviceId` must point to a `Device` whose `deviceTypeEnumId`
matches `DeviceConfig.deviceTypeEnumId`.

This is the rule that guarantees that a type-level configuration template can
be safely applied to a specific device instance.

## Group-level rule

`DeviceConfigSet` is the analogue of `DeviceConfig` for a `DeviceGroup`.

Typical meaning:

- `DeviceConfig`
  - config template for one device type
- `DeviceConfigSet`
  - set of compatible member configs for one logical subsystem / device group

`DeviceConfigSetMember` rows sequence or describe the member configs that
participate in the set.

## Recommended authoring order

1. create atomic `Device` / `PhysicalDevice`
2. create shared `ParameterDef`
3. create `Parameter`
4. create `DeviceGroup` / `DeviceGroupMember`
5. create one `DeviceConfig` template per relevant `deviceTypeEnumId`
6. create one `DeviceConfigSet` when a `DeviceGroup` needs a grouped recipe
7. create `DeviceConfigSetMember` rows to compose the set
8. create one `DeviceRuleSet`
9. create `DeviceRule` rows that bind each `DeviceConfig` to the specific `Device`

## Practical interpretation

The skill should treat recipe loading as a two-level pattern:

- type-level configuration definition:
  - `DeviceConfig`
  - `DeviceConfigSet`
- instance-level application:
  - `DeviceRule`
  - `DeviceRuleSet`

The skill should therefore ask:

- which device types need a reusable config template?
- which device groups need a config set?
- which specific devices should receive which config?
- in what priority order should the rules be applied?
