(*
 * Equality of two axis group positions. SMC_POS_REF is a union: the Cartesian view c (X, Y, Z, A, B, C)
 * covers the same six values as the per-axis view, so comparing c compares both.
 *)
FUNCTION posRefEqual : BOOL
	VAR_INPUT
		a : SM3_Robotics.SMC_POS_REF;
		b : SM3_Robotics.SMC_POS_REF;
	END_VAR

	posRefEqual := (a.c.X = b.c.X) AND (a.c.Y = b.c.Y) AND (a.c.Z = b.c.Z)
		AND (a.c.A = b.c.A) AND (a.c.B = b.c.B) AND (a.c.C = b.c.C);
	END_FUNCTION
