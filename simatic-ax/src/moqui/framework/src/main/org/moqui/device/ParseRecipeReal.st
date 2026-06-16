USING System.Strings;

FUNCTION ParseRecipeReal : REAL
	VAR_INPUT
		value : STRING;
	END_VAR
	VAR_TEMP
		position : INT;
		startPosition : INT := INT#1;
		charText : STRING[1];
		sign : REAL := REAL#1.0;
		digit : REAL;
		decimalSeen : BOOL;
		fractionScale : REAL := REAL#1.0;
		valueLength : INT;
	END_VAR

	valueLength := LengthOf(value);
	IF valueLength <= INT#0 THEN
		RETURN;
	END_IF;

	charText := Substring(value, INT#1, INT#1);
	IF charText = '-' THEN
		sign := REAL#-1.0;
		startPosition := INT#2;
	ELSIF charText = '+' THEN
		startPosition := INT#2;
	END_IF;

	FOR position := startPosition TO valueLength DO
		charText := Substring(value, position, INT#1);
		IF charText = '.' THEN
			decimalSeen := TRUE;
		ELSE
			CASE charText OF
				'0' : digit := REAL#0.0;
				'1' : digit := REAL#1.0;
				'2' : digit := REAL#2.0;
				'3' : digit := REAL#3.0;
				'4' : digit := REAL#4.0;
				'5' : digit := REAL#5.0;
				'6' : digit := REAL#6.0;
				'7' : digit := REAL#7.0;
				'8' : digit := REAL#8.0;
				'9' : digit := REAL#9.0;
			ELSE
				EXIT;
			END_CASE;

			IF NOT decimalSeen THEN
				ParseRecipeReal := (ParseRecipeReal * REAL#10.0) + digit;
			ELSE
				fractionScale := fractionScale * REAL#10.0;
				ParseRecipeReal := ParseRecipeReal + (digit / fractionScale);
			END_IF;
		END_IF;
	END_FOR;

	ParseRecipeReal := ParseRecipeReal * sign;
END_FUNCTION
