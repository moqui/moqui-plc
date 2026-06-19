USING System.Strings;

FUNCTION ParseRecipeDInt : DINT
	VAR_INPUT
		value : STRING;
	END_VAR
	VAR_TEMP
		position : INT;
		startPosition : INT := INT#1;
		charText : STRING[1];
		sign : DINT := DINT#1;
		digit : DINT;
		valueLength : INT;
	END_VAR

	valueLength := LengthOf(value);
	IF valueLength <= INT#0 THEN
		RETURN;
	END_IF;

	charText := Substring(value, INT#1, INT#1);
	IF charText = '-' THEN
		sign := -DINT#1;
		startPosition := INT#2;
	ELSIF charText = '+' THEN
		startPosition := INT#2;
	END_IF;

	FOR position := startPosition TO valueLength DO
		charText := Substring(value, position, INT#1);
		CASE charText OF
			'0' : digit := DINT#0;
			'1' : digit := DINT#1;
			'2' : digit := DINT#2;
			'3' : digit := DINT#3;
			'4' : digit := DINT#4;
			'5' : digit := DINT#5;
			'6' : digit := DINT#6;
			'7' : digit := DINT#7;
			'8' : digit := DINT#8;
			'9' : digit := DINT#9;
		ELSE
			EXIT;
		END_CASE;
		ParseRecipeDInt := (ParseRecipeDInt * DINT#10) + digit;
	END_FOR;

	ParseRecipeDInt := ParseRecipeDInt * sign;
END_FUNCTION
