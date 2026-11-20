CONFIGURATION moqui
    VAR_GLOBAL CONSTANT
        (* ========== Framework ========== *)
        	(* Exact Device.deviceId of this dedicated application. *)
        	applicationDeviceId : STRING := 'HVAC_DEMO_PLC';

        	retryOnError : BOOL := TRUE;
        	(* Minimum time between retries after an error, in seconds *)
        	minRetryTime : UINT := UINT#10;
        	(* If specified only retry this many times. When this count is reached MoquiStart stays in Error until a reset from the supervision. *)
        	maxRetryCount : UINT := UINT#5;

        (* ========== Logger ========== *)

        	(* Logger facade configurations *)
        	LOG_MAX_SIZE : UINT := UINT#100;
        	defaultLogLevel : LogLevel := LogLevel#Debug;
        	(* Window in which equal consecutive events are only counted (T#0S disables suppression) *)
        	defaultLogSuppressDuration : TIME := T#10S;
        	defaultLogSuppressDuplicates : BOOL := TRUE;
        	(*
        	 * Rate limit: maximum new events stored by one logger in one defaultLogSuppressDuration window (0 disables).
        	 * Further events are only counted and reported by one Warn event at the end of the window.
        	 * A safety net against loggers called at every cycle: devices log events on edges.
        	 *)
        	defaultLogMaxEventsPerWindow : UINT := UINT#20;
        	(* Log appender configurations *)
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
            AXIS_IN_VELOCITY_TOLERANCE : LREAL := LREAL#0.02;

        	(* ========== Motion ========== *)

        	(*
        	 * Maximum number of waypoints in a single Trajectory struct.
        	 * Each point holds one SMC_POS_REF (6 LREAL = 48 bytes) plus metadata.
        	 * Increase if longer trajectories are needed.
        	 *)
        	TRAJECTORY_POINT_LIST_MAX_SIZE : DINT := DINT#64;
    END_VAR

    VAR_GLOBAL
        (* Timing generation *)
            clks : Clocks;

        	(*
        	 * Framework args.
        	 * External framework commands and configurations set by Moqui or supervision.
             *)
        	enable : BOOL := TRUE;
        	init : BOOL := TRUE; (* It could be the powerOn signal*)
        	fault, error, commError, reset, autoReset : BOOL;
        	(* All device configs loaded *)
        	allConfigLoaded : BOOL;
        	retryCount, retryTime : UINT;
        	isPrimary : BOOL;
        	heartbeat : ULINT;

            (* Array of reference to local logs used by the log appender *)
            logSourceList : ARRAY[1..LOG_SOURCE_LIST_MAX_SIZE] OF LogSource;
            (* Registered LoggerFacade buffers; incremented atomically, may exceed LOG_SOURCE_LIST_MAX_SIZE when the list is full *)
            logSourceListSize : DINT := DINT#0;
            (*
             * Lowest level written by every LoggerFacade (Trace, Debug, Info, Warn, Error, Fatal; All = Trace; Off = none).
             * Debug keeps the FSM and device events of the demo; Info is advisable in production.
             *)
            logMinLevel : LogLevel := LogLevel#Debug;

        	(* Facade for managing devices and logical parameters. *)
        	dev : DeviceFacade;

        	(* Motion override - written by Moqui via liveParamsSub *)
        	trjDynamicSlowdownEnable : BOOL := FALSE;
        	trjDynamicSlowdownFactor : REAL := REAL#1.0;
        	abortCurrentTrajectory : BOOL := FALSE;
    END_VAR

    TASK StartTask(INTERVAL := T#10ms, PRIORITY := 1);
    TASK TestTask(INTERVAL := T#10ms, PRIORITY := 2);
    PROGRAM MoquiStartInstance WITH StartTask : MoquiStart;
    PROGRAM HvacTestSuiteInstance WITH TestTask : HvacTestSuite;
END_CONFIGURATION
