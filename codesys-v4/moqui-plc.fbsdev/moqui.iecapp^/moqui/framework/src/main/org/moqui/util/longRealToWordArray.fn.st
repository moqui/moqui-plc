(*
 * Convert a long real variable to a word array.
 * The words carry the IEEE 754 bit pattern: result[0] is the most significant word,
 * bigEndian = TRUE reverses the word order. longWordToLongReal is the inverse.
 *)
FUNCTION longRealToWordArray : ARRAY[0..3] OF WORD
	VAR_INPUT
	    value : LREAL;
	    bigEndian : BOOL := FALSE;
	END_VAR
	VAR
	    bits : LongRealBits;
	    result : ARRAY[0..3] OF WORD;
	END_VAR

	bits.lrealValue := value;
	IF bigEndian THEN
	    bits.lwordValue := swapLWordEndian(bits.lwordValue);
	END_IF;

	result[0] := TO_WORD(SHR(bits.lwordValue, 48));
	result[1] := TO_WORD(SHR(bits.lwordValue, 32) AND 16#FFFF);
	result[2] := TO_WORD(SHR(bits.lwordValue, 16) AND 16#FFFF);
	result[3] := TO_WORD(bits.lwordValue AND 16#FFFF);
	longRealToWordArray := result;
	END_FUNCTION
