(*
 * Convert a real variable to a word array.
 * The words carry the IEEE 754 bit pattern: result[0] is the most significant word,
 * bigEndian = TRUE reverses the word order. doubleWordToReal is the inverse.
 *)
FUNCTION realToWordArray : ARRAY[0..1] OF WORD
	VAR_INPUT
	    value : REAL;
	    bigEndian : BOOL := FALSE;
	END_VAR
	VAR
	    bits : RealBits;
	    result : ARRAY[0..1] OF WORD;
	END_VAR

	bits.realValue := value;
	IF bigEndian THEN
	    bits.dwordValue := swapDWordEndian(bits.dwordValue);
	END_IF;
	result[0] := TO_WORD(SHR(bits.dwordValue, 16));
	result[1] := TO_WORD(bits.dwordValue AND 16#FFFF);
	realToWordArray := result;
	END_FUNCTION
