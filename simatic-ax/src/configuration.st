CONFIGURATION moqui
    VAR_GLOBAL CONSTANT
        (* ========== Framework ========== *)

        	retryOnError : BOOL := TRUE;
        	(* Minimum time between retries after an error, in seconds *)
        	minRetryTime : UINT := UINT#10;
        	(* If specified only retry this many times. When this count is reached paused will be set to true. *)
        	maxRetryCount : UINT := UINT#5;

        (* ========== Logger ========== *)

        	LOG_MAX_SIZE : UINT := UINT#100;
        	defaultLogLevel : LogLevel := LogLevel#Debug;
        	defaultLogSuppressDuration : TIME := T#0S; (* T#10s; *)
        	defaultLogSuppressDuplicates : BOOL := TRUE;
        	LOG_SOURCE_LIST_MAX_SIZE : UINT := UINT#50;

        (* ========== Signal Management ========== *)

        	(* Signal configurations *)
        	SIGNAL_LIST_MAX_SIZE : UINT := UINT#200;

        (* ========== Device Config Management ========== *)

        	DEVICE_CONFIG_LIST_MAX_SIZE : UINT := UINT#100;
        	defaultConfigType : STRING := 'HvacDeviceConfig';  (* 'TestRecipes' *)
        	(*
        	 * Storage path for recipe files used by RecipeManCommands.SetStoragePath.
        	 * The path is relative to the application directory (PlcLogic/<AppName>/).
        	 * CODESYS IDE Recipe Manager deploys files to PlcLogic/ root with prefix "recipes",
        	 * so move them into PlcLogic/<AppName>/recipes/ to match this default,
        	 * or set to '../' to read directly from PlcLogic/ without moving files.
        	 *)
        	deviceConfigStoragePath : STRING := '';
        	ACTUATOR_GROUP_MAX_SIZE : UINT := UINT#8;
            AXIS_IN_VELOCITY_TOLERANCE : LREAL := 0.02;

        	(* ========== Motion ========== *)

        	(*
        	 * Maximum number of waypoints in a single Trajectory struct.
        	 * Each point holds one SMC_POS_REF (6 LREAL = 48 bytes) plus metadata.
        	 * Increase if longer trajectories are needed.
        	 *)
        	TRAJECTORY_POINT_LIST_MAX_SIZE : DINT := 64;
    END_VAR

    VAR_GLOBAL
        (* Timing generation *)
            clks : Clocks;

        	enable : BOOL := TRUE;
        	init : BOOL := TRUE; (* It could be the powerOn signal*)
        	fault, error, commError, reset, autoReset : BOOL;
        	(* All device configs loaded *)
        	allConfigLoaded : BOOL;
        	retryCount, retryTime : UINT;
        	isPrimary : BOOL;
        	heartbeat : ULINT;

            logSourceList : ARRAY[1..LOG_SOURCE_LIST_MAX_SIZE] OF LogSource;
            logSourceListSize : UINT := UINT#0;

        	(* Facade for managing devices and logical parameters. *)
        	dev : DeviceFacade;
    END_VAR

    TASK StartTask(INTERVAL := T#10ms, PRIORITY := 1);
    TASK TestTask(INTERVAL := T#10ms, PRIORITY := 2);
    PROGRAM MoquiStartInstance WITH StartTask : MoquiStart;
    PROGRAM HvacTestSuiteInstance WITH TestTask : HvacTestSuite;
END_CONFIGURATION
