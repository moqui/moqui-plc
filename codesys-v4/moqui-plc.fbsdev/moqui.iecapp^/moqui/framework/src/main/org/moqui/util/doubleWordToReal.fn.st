(*
 * Utility function to convert a word array to a real variable.
 * The words carry the IEEE 754 bit pattern: wordArray[0] is the most significant word,
 * bigEndian = TRUE reverses the word order. realToWordArray is the inverse.
 *)
FUNCTION doubleWordToReal : REAL
	VAR_INPUT
		wordArray : ARRAY[0..1] OF WORD;
		bigEndian : BOOL := FALSE;
	END_VAR
	VAR
	    bits : RealBits;
	END_VAR

	bits.dwordValue := SHL(TO_DWORD(wordArray[0]), 16) OR TO_DWORD(wordArray[1]);
	IF bigEndian THEN
	    bits.dwordValue := swapDWordEndian(bits.dwordValue);
	END_IF;
	doubleWordToReal := bits.realValue;
	END_FUNCTION
