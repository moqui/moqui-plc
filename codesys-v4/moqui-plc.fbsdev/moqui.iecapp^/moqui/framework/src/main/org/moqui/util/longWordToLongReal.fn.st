(*
 * Utility function to convert a word array to a long real variable.
 * The words carry the IEEE 754 bit pattern: wordArray[0] is the most significant word,
 * bigEndian = TRUE reverses the word order. longRealToWordArray is the inverse.
 *)
FUNCTION longWordToLongReal : LREAL
	VAR_INPUT
		wordArray : ARRAY[0..3] OF WORD;
		bigEndian : BOOL := FALSE;
	END_VAR
	VAR
		bits : LongRealBits;
	END_VAR

	bits.lwordValue := TO_LWORD(wordArray[0]);
	bits.lwordValue := SHL(bits.lwordValue, 16) OR TO_LWORD(wordArray[1]);
	bits.lwordValue := SHL(bits.lwordValue, 16) OR TO_LWORD(wordArray[2]);
	bits.lwordValue := SHL(bits.lwordValue, 16) OR TO_LWORD(wordArray[3]);
	IF bigEndian THEN
	    bits.lwordValue := swapLWordEndian(bits.lwordValue);
	END_IF;
	longWordToLongReal := bits.lrealValue;
	END_FUNCTION
