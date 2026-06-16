TYPE ActuatorType : (
  OnOff, (* Fallback value *)
  Contactor,
  SoftStarter,
  Vfd, (* Frequency converter / Inverter drive *)
  PneumaticCylinder,
  PneumaticValve,
  HydraulicCylinder,
  HydraulicValve,
  Damper,
  SolenoidValve
  (* etc. *)
); END_TYPE
