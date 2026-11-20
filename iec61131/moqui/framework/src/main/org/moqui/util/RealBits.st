(*
 * Bit pattern of a REAL. TO_REAL(DWORD) and TO_DWORD(REAL) convert the numeric value;
 * a field-bus float needs the IEEE 754 bits unchanged, which this union gives.
 *)
TYPE RealBits : UNION
	realValue : REAL;
	dwordValue : DWORD;
END_UNION END_TYPE
