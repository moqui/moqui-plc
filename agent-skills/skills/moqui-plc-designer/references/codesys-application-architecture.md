# CODESYS Application architecture

Use one isolated CODESYS `Application` for every top-level controlled system.
CODESYS permits multiple uniquely named Application objects below one PLC device;
each Application contains its own POUs, libraries, global variables and Task
Configuration.

In the Moqui model each Application is a distinct `Device` plus
`PhysicalDevice`, analogous to a separate CPU in a hardware PLC rack. A rack or
project may therefore contain several controller PhysicalDevices. Sampling
domains and gateway requests must identify the owning controller explicitly.

For every generated Application:

- include one dedicated copy of `iec61131/moqui/framework`;
- include one runtime component under `runtime/component/<component>`;
- keep exactly one supervisor `Main`, `MainRuleEngine`, `DeviceFacade`,
  `DeviceManager` and `DeviceDiagnostics`;
- generate subsystem FSMs as uniquely named controller/status pairs;
- call subsystem controllers sequentially by ascending `call_sequence`;
- call `DeviceManager` once, after all subsystem controllers;
- let the developer create control/communication tasks and the device tree;
- let the developer verify connected devices and select the Application used for
  device I/O when multiple Applications share the same PLC device.

Official reference:
https://content.helpme-codesys.com/en/CODESYS%20Development%20System/_cds_obj_application.html
