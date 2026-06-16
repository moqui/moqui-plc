(* After each creation, saving or deletion of device config it will be necessary to reload the config list with the Init command. *)
TYPE DeviceConfigCmdType : (
    Init, (* Init the recipe management component *)
	Create,
    Save,
	Load,
	Delete,
	Reset
); END_TYPE
