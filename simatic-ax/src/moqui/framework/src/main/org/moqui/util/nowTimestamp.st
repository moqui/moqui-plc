USING Siemens.Simatic.S71500.Clocks;

(*
 * Current date and time in UTC, from the system clock of the CPU.
 * Log events carry UTC: the gateway reads a date as UTC, and UTC has no repeated hour at the daylight
 * saving change. Convert to local time only for display.
 *)
FUNCTION nowTimestamp : DATE_AND_TIME
	VAR
		systemDateTime : LDATE_AND_TIME;
	END_VAR

	GetSystemDateTime(value => systemDateTime);
	nowTimestamp := TO_DT(systemDateTime);
	END_FUNCTION
