(*
 * Equality of two axis group positions (AX override).
 * In AX CoordMotion.SMC_POS_REF is a flat Cartesian struct: the six values are compared directly.
 * The CODESYS source compares the Cartesian view c of the SMC_POS_REF union.
 *)
FUNCTION posRefEqual : BOOL
	VAR_INPUT
		a : CoordMotion.SMC_POS_REF;
		b : CoordMotion.SMC_POS_REF;
	END_VAR

	posRefEqual := (a.X = b.X) AND (a.Y = b.Y) AND (a.Z = b.Z)
		AND (a.A = b.A) AND (a.B = b.B) AND (a.C = b.C);
	END_FUNCTION
