TYPE ActuatorActuationType : (
    SingleActuation, (* Single Actuation: Uses enable output only *)
    DoubleActuation, (* Double Actuation: enable/disable are pulses *)
    DoubleActuationNoRetain (* Double Actuation: enable/disable are levels *)
); END_TYPE
