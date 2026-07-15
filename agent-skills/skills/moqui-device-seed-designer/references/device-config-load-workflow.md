# DeviceConfig load workflow

1. Define physical/logical Devices and explicit DeviceGroups.
2. Define the shared `ParameterDef` catalog.
3. Create atomic `DeviceConfig` templates and configuration-scoped Parameters.
4. Create a `DeviceRuleSet` rooted at the intended Device or DeviceGroup.
5. Add one `DeviceRule` per target/configuration operation.
6. Review target scope, device-type compatibility, operation type and unique
   ascending priority.
7. Approve the model before generating final seed data.

The rules may apply, suggest, assert, check compliance or soft-validate a
configuration. Runtime behavior is selected by `ruleTypeEnumId`; the seed
designer only materializes the reviewed data model.
