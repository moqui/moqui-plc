USING Siemens.Simatic.S71500.Clocks;

FUNCTION nowTimestamp : DATE_AND_TIME
	VAR
		localDateTime : LDATE_AND_TIME;
		execResult : WORD;
	END_VAR

	nowTimestamp := DT#1970-01-01-00:00:00;
	execResult := GetLocalDateTime(value => localDateTime);
	IF (execResult = WORD#16#0000) OR (execResult = WORD#16#0001) THEN
		nowTimestamp := TO_DT(localDateTime);
	END_IF;
	END_FUNCTION
