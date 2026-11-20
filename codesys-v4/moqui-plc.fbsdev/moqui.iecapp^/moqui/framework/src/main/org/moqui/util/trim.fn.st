FUNCTION trim : STRING
	VAR_INPUT
	    inputString : STRING;
	END_VAR
	VAR
	    startPos, endPos : INT;
	    stringLength : INT;
	    currentChar : STRING(1);
	END_VAR

	stringLength := LEN(inputString);
	startPos := 1;

	(*
	 * Skip leading whitespace (space, tab = 9, LF = 10, CR = 13).
	 * The character is compared as text: TO_INT of a one-character string parses it as a number.
	 * MID(STR, LEN, POS) as in IEC 61131-3 and CODESYS: length before position.
	 *)
	WHILE (startPos <= stringLength) DO
	    currentChar := MID(inputString, 1, startPos);
	    IF (currentChar <> ' ') AND (currentChar <> '$T')
				AND (currentChar <> '$L') AND (currentChar <> '$R') THEN
	        EXIT;
	    END_IF;

	    startPos := startPos + 1;
	END_WHILE;

	(* Skip trailing whitespace *)
	endPos := stringLength;
	WHILE (endPos > 0) DO
	    currentChar := MID(inputString, 1, endPos);
	    IF (currentChar <> ' ') AND (currentChar <> '$T')
				AND (currentChar <> '$L') AND (currentChar <> '$R') THEN
	        EXIT;
	    END_IF;

	    endPos := endPos - 1;
	END_WHILE;

	(* Extract the trimmed substring *)
	IF startPos <= endPos THEN
	    trim := MID(inputString, endPos - startPos + 1, startPos);
	ELSE
	    trim := ''; (* All characters were whitespace *)
	END_IF;
	END_FUNCTION
