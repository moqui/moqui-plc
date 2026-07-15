# Controller and DeviceGroup model

Each hardware CPU and each CODESYS Application is represented by its own
`Device`/`PhysicalDevice` pair. This mirrors a hardware rack with multiple CPUs:
the rack/project is a logical grouping boundary, while every CPU/Application has
an independent runtime, framework copy, task configuration and device tree.

Every sampling domain declares `controller_device_id`. Requests, OPC UA
connections and PLC4J connections are consequently attached to the controller
that owns the I/O namespace.

DeviceGroups and membership are never inferred from the system decomposition.
The developer declares every group, member role and sequence in
`device-groups-survey.yaml`; the generator only validates and materializes that
decision. Redundancy behavior and physical binding remain outside scope.
