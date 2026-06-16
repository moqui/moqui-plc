(* Drive control words *)
(* Relevant control word for start, stop and reset commands *)
TYPE DriveControlWord : (
	(* ABB ACS580, ACH580 drive *) 
	ABBACH580Reset,
	ABBACH580Stop,
	ABBACH580Start,
	(* Control Techniques M600 drive *)
	CTM600Reset,
	CTM600Stop,
	CTM600Start,
	(* Danfoss FC102 drive *)
	DanfossFC102Reset,
	DanfossFC102Stop,
	DanfossFC102Start
); END_TYPE
