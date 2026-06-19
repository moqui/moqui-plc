USING System.Strings;

FUNCTION ParseRecipeTime : TIME
	VAR_INPUT
		value : STRING;
	END_VAR
	VAR_TEMP
		normalizedValue : STRING[32];
		numberText : STRING[16];
		unitText : STRING[2];
		valueLength : INT;
		magnitude : DINT;
		position : DINT;
	END_VAR

	normalizedValue := value;
	valueLength := LengthOf(normalizedValue);

	IF (valueLength >= INT#5) AND (Substring(normalizedValue, INT#1, INT#5) = 'TIME#') THEN
		normalizedValue := Substring(normalizedValue, INT#6, valueLength - INT#5);
	ELSIF (valueLength >= INT#2) AND (Substring(normalizedValue, INT#1, INT#2) = 'T#') THEN
		normalizedValue := Substring(normalizedValue, INT#3, valueLength - INT#2);
	END_IF;

	valueLength := LengthOf(normalizedValue);
	IF valueLength <= INT#0 THEN
		RETURN;
	END_IF;

	IF (valueLength >= INT#2) AND (Substring(normalizedValue, valueLength - INT#1, INT#2) = 'ms') THEN
		unitText := 'ms';
		numberText := Substring(normalizedValue, INT#1, valueLength - INT#2);
	ELSIF (valueLength >= INT#1) THEN
		unitText := Substring(normalizedValue, valueLength, INT#1);
		numberText := Substring(normalizedValue, INT#1, valueLength - INT#1);
	END_IF;

	magnitude := ParseRecipeDInt(numberText);
	IF magnitude <= DINT#0 THEN
		RETURN;
	END_IF;

	CASE unitText OF
		'ms' :
			FOR position := DINT#1 TO magnitude DO
				ParseRecipeTime := ParseRecipeTime + T#1ms;
			END_FOR;
		's' :
			FOR position := DINT#1 TO magnitude DO
				ParseRecipeTime := ParseRecipeTime + T#1s;
			END_FOR;
		'm' :
			FOR position := DINT#1 TO magnitude DO
				ParseRecipeTime := ParseRecipeTime + T#1m;
			END_FOR;
		'h' :
			FOR position := DINT#1 TO magnitude DO
				ParseRecipeTime := ParseRecipeTime + T#1h;
			END_FOR;
	END_CASE;
END_FUNCTION
