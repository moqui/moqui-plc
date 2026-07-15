# DeviceConfig semantics

`DeviceConfig` is an atomic, reusable configuration for one compatible
`deviceTypeEnumId`; it is not the live snapshot of a device. Its declared
values are `Parameter` rows scoped by `deviceConfigId` and reuse the same
`ParameterDef` catalog as device-bound values.

Multi-device composition is represented only by `DeviceRuleSet` and
`DeviceRule`:

- the rule set defines a root Device or DeviceGroup scope;
- every rule binds one atomic `DeviceConfig` to one target Device;
- `priority` defines deterministic application order;
- a target must be the root itself or a member reachable from the explicit
  DeviceGroup membership graph;
- configuration and target device types must be compatible.

The fixed configuration catalog is derived from recipe-suitable `VAR_INPUT`
fields. Exclude `VAR_IN_OUT`, physical feedback, transient runtime values and
device-tree references. Use conservative defaults for control-like inputs and
numeric constants for PLC enums.

Recommended defaults are `DctApplyConfig`, `DcpPrototypeConfig`,
`DrspConfiguration`, and `DrtApplyConfig`. Concrete values, scope and priority
must be reviewed and approved by the PLC developer.
