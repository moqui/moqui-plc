FUNCTION truncReal : REAL
	VAR_INPUT
	    inputValue : REAL;
	    decimals : INT;
	END_VAR
	VAR
	    factor : REAL;
	END_VAR

	factor := TO_REAL(EXP(LN(10.0) * TO_REAL(decimals)));
	truncReal := TO_REAL(TRUNC(inputValue * factor)) / factor;
	END_FUNCTION
