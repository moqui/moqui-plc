FUNCTION_BLOCK ProcessPid
VAR_INPUT
    enable : BOOL;
    reset : BOOL;
    controlSystemId : STRING;
    controlSystemName : STRING;
    feedback : REAL;
    feedbackMultiplier : REAL := REAL#1.0;
    setpoint : REAL;
    atSetpointHysteresis : REAL;
    setpointMultiplier : REAL := REAL#1.0;
    setpointMin : REAL;
    setpointMax : REAL;
    setpointRampType : RampType := RampType#Linear;
    setpointIncreaseTime : TIME := T#0S;
    setpointDecreaseTime : TIME := T#0S;
    setpointFreezeEnable : BOOL;
    deviationInversion : BOOL;
    outputMin : REAL;
    outputMax : REAL;
    outputFreezeEnable : BOOL;
    gain : REAL := REAL#1.0;
    integrationTime : REAL := REAL#0.0;
    derivationTime : REAL := REAL#0.0;
    offset : REAL := REAL#0.0;
    deadbandRange : REAL;
    deadbandDelay : TIME;
    sleepLevel : REAL := REAL#0.0;
    sleepDelay : TIME;
    wakeupDeviation : REAL;
    wakeupDelay : TIME;
    sleepBoostLevel : REAL := REAL#0.0;
    sleepBoostTime : TIME;
    trackingMode : BOOL := FALSE;
    trackingRef : REAL := REAL#0.0;
    clock : BOOL;
    tickTime : TIME := T#10ms;
    setpointEpsilon : REAL := REAL#0.000001;
END_VAR
VAR_OUTPUT
    feedbackActual : REAL;
    setpointActual : REAL;
    deviationActual : REAL;
    outputActual : REAL;
    invalidConfig : BOOL;
    active : BOOL;
    atSetpoint : BOOL;
    zeroOutput : BOOL;
    setpointFrozen : BOOL;
    outputFrozen : BOOL;
    sleepMode : BOOL;
    sleepBoost : BOOL;
    deadband : BOOL;
    tracking : BOOL;
    outputLimitsActive : BOOL;
    overflow : BOOL;
    loggerName : STRING;
END_VAR
VAR
    deadbandCounter : UDINT;
    sleepCounter : UDINT;
    wakeupCounter : UDINT;
    sleepBoostCounter : UDINT;
    integralTerm : REAL;
    previousDeviation : REAL;
    previousOutput : REAL;
    lastOutput : REAL;
    lastPidOutput : REAL;
    setpointTarget : REAL;
    setpointInternal : REAL;
    lastSetpoint : REAL;
    lastSetpointTarget : REAL;
    prevReset : BOOL;
    resetEdge : BOOL;
    manualMode : BOOL;
    yManual : REAL;
    sleepReq : BOOL;
    wakeupReq : BOOL;
    startRamp : BOOL;
    proportionalTerm : REAL;
    derivativeTerm : REAL;
    deltaDeviation : REAL;
    rawOutput : REAL;
    deviationMagnitude : REAL;
    deltaTime : REAL;
    spRange : REAL;
    increaseTicks : UDINT;
    decreaseTicks : UDINT;
    delayTicks : UDINT;
    rampStep : REAL;
    remainingTime : TIME;
    logger : LoggerFacade;
    sShapedFunc : SShapedFunc;
    expRamp : IIRFilter;
END_VAR

loggerName := controlSystemName;
logger.enable := TRUE;
logger.loggerName := loggerName;

resetEdge := reset AND NOT prevReset;
prevReset := reset;

invalidConfig := FALSE;
overflow := FALSE;
outputLimitsActive := FALSE;
tracking := FALSE;

IF tickTime <= T#0S THEN
    invalidConfig := TRUE;
    active := FALSE;
    outputActual := REAL#0.0;
    RETURN;
END_IF;

IF (gain <= REAL#0.0)
        OR (integrationTime < REAL#0.0)
        OR (derivationTime < REAL#0.0)
        OR (setpointMin > setpointMax)
        OR (outputMin > outputMax) THEN
    invalidConfig := TRUE;
    active := FALSE;
    outputActual := REAL#0.0;
    logger(message := 'Invalid PID configuration.', level := LogLevel#Error);
    RETURN;
END_IF;

IF NOT enable THEN
    active := FALSE;
    atSetpoint := FALSE;
    zeroOutput := TRUE;
    setpointFrozen := FALSE;
    outputFrozen := FALSE;
    sleepMode := FALSE;
    sleepBoost := FALSE;
    deadband := FALSE;
    outputActual := REAL#0.0;
    lastOutput := REAL#0.0;
    previousOutput := REAL#0.0;
    lastPidOutput := REAL#0.0;
    deadbandCounter := UDINT#0;
    sleepCounter := UDINT#0;
    wakeupCounter := UDINT#0;
    sleepBoostCounter := UDINT#0;
    integralTerm := REAL#0.0;
    previousDeviation := REAL#0.0;
    sShapedFunc(execute := FALSE, clock := FALSE);
    expRamp(execute := FALSE, clock := FALSE, reset := TRUE, input := REAL#0.0, T := REAL#0.001);
    RETURN;
END_IF;

active := TRUE;

IF resetEdge THEN
    setpointInternal := REAL#0.0;
    lastSetpoint := REAL#0.0;
    lastSetpointTarget := REAL#0.0;
    previousDeviation := REAL#0.0;
    previousOutput := REAL#0.0;
    lastOutput := REAL#0.0;
    lastPidOutput := REAL#0.0;
    integralTerm := REAL#0.0;
    deadbandCounter := UDINT#0;
    sleepCounter := UDINT#0;
    wakeupCounter := UDINT#0;
    sleepBoostCounter := UDINT#0;
    sleepMode := FALSE;
    sleepBoost := FALSE;
    sShapedFunc(execute := FALSE, clock := FALSE);
    expRamp(execute := FALSE, clock := FALSE, reset := TRUE, input := REAL#0.0, T := REAL#0.001);
    logger(message := 'Reset process PID.', level := LogLevel#Warn);
END_IF;

IF controlSystemName = '' THEN
    loggerName := controlSystemId;
ELSE
    loggerName := controlSystemName;
END_IF;
logger.loggerName := loggerName;

feedbackActual := feedback * feedbackMultiplier;

IF setpointFreezeEnable THEN
    setpointTarget := lastSetpoint;
ELSE
    setpointTarget := setpoint * setpointMultiplier;
    IF setpointTarget < setpointMin THEN
        setpointTarget := setpointMin;
    ELSIF setpointTarget > setpointMax THEN
        setpointTarget := setpointMax;
    END_IF;
END_IF;

setpointFrozen := setpointFreezeEnable;
startRamp := FALSE;
deviationMagnitude := setpointTarget - lastSetpointTarget;
IF deviationMagnitude < REAL#0.0 THEN
    deviationMagnitude := -deviationMagnitude;
END_IF;
IF (deviationMagnitude > setpointEpsilon) OR resetEdge THEN
    startRamp := TRUE;
END_IF;
lastSetpointTarget := setpointTarget;

IF (setpointIncreaseTime > T#0S) AND (setpointDecreaseTime > T#0S) THEN
    CASE setpointRampType OF
        RampType#SShaped:
            IF setpointTarget >= lastSetpoint THEN
                remainingTime := setpointIncreaseTime;
            ELSE
                remainingTime := setpointDecreaseTime;
            END_IF;

            sShapedFunc(
                execute := startRamp OR sShapedFunc.busy,
                clock := clock,
                startValue := lastSetpoint,
                endValue := setpointTarget,
                duration := remainingTime,
                tickTime := tickTime
            );

            IF sShapedFunc.error THEN
                setpointInternal := setpointTarget;
            ELSE
                setpointInternal := sShapedFunc.output;
            END_IF;

        RampType#Exponential:
            IF setpointTarget >= lastSetpoint THEN
                remainingTime := setpointIncreaseTime;
            ELSE
                remainingTime := setpointDecreaseTime;
            END_IF;

            delayTicks := UDINT#0;
            WHILE remainingTime > T#0S DO
                delayTicks := delayTicks + UDINT#1;
                IF remainingTime > tickTime THEN
                    remainingTime := remainingTime - tickTime;
                ELSE
                    remainingTime := T#0S;
                END_IF;
            END_WHILE;

            IF delayTicks = UDINT#0 THEN
                deltaTime := REAL#0.001;
            ELSE
                deltaTime := TO_REAL(delayTicks) / REAL#4.605;
                IF deltaTime < REAL#0.001 THEN
                    deltaTime := REAL#0.001;
                END_IF;
            END_IF;

            expRamp(
                execute := TRUE,
                clock := clock,
                reset := startRamp,
                input := setpointTarget,
                T := deltaTime,
                tickTime := tickTime
            );

            IF expRamp.error THEN
                setpointInternal := setpointTarget;
            ELSE
                setpointInternal := expRamp.output;
            END_IF;

        ELSE
            spRange := setpointMax - setpointMin;
            IF spRange < REAL#1.0 THEN
                spRange := REAL#1.0;
            END_IF;

            remainingTime := setpointIncreaseTime;
            increaseTicks := UDINT#0;
            WHILE remainingTime > T#0S DO
                increaseTicks := increaseTicks + UDINT#1;
                IF remainingTime > tickTime THEN
                    remainingTime := remainingTime - tickTime;
                ELSE
                    remainingTime := T#0S;
                END_IF;
            END_WHILE;
            IF increaseTicks = UDINT#0 THEN
                increaseTicks := UDINT#1;
            END_IF;

            remainingTime := setpointDecreaseTime;
            decreaseTicks := UDINT#0;
            WHILE remainingTime > T#0S DO
                decreaseTicks := decreaseTicks + UDINT#1;
                IF remainingTime > tickTime THEN
                    remainingTime := remainingTime - tickTime;
                ELSE
                    remainingTime := T#0S;
                END_IF;
            END_WHILE;
            IF decreaseTicks = UDINT#0 THEN
                decreaseTicks := UDINT#1;
            END_IF;

            setpointInternal := lastSetpoint;
            IF clock THEN
                IF setpointTarget > lastSetpoint THEN
                    rampStep := spRange / TO_REAL(increaseTicks);
                    setpointInternal := lastSetpoint + rampStep;
                    IF setpointInternal > setpointTarget THEN
                        setpointInternal := setpointTarget;
                    END_IF;
                ELSIF setpointTarget < lastSetpoint THEN
                    rampStep := spRange / TO_REAL(decreaseTicks);
                    setpointInternal := lastSetpoint - rampStep;
                    IF setpointInternal < setpointTarget THEN
                        setpointInternal := setpointTarget;
                    END_IF;
                END_IF;
            END_IF;
    END_CASE;
ELSE
    setpointInternal := setpointTarget;
END_IF;

lastSetpoint := setpointInternal;
setpointActual := setpointInternal;

IF deviationInversion THEN
    deviationActual := feedbackActual - setpointActual;
ELSE
    deviationActual := setpointActual - feedbackActual;
END_IF;

deviationMagnitude := deviationActual;
IF deviationMagnitude < REAL#0.0 THEN
    deviationMagnitude := -deviationMagnitude;
END_IF;

remainingTime := deadbandDelay;
delayTicks := UDINT#0;
WHILE remainingTime > T#0S DO
    delayTicks := delayTicks + UDINT#1;
    IF remainingTime > tickTime THEN
        remainingTime := remainingTime - tickTime;
    ELSE
        remainingTime := T#0S;
    END_IF;
END_WHILE;

IF (deadbandRange > REAL#0.0) AND (deviationMagnitude <= deadbandRange) THEN
    IF clock THEN
        deadbandCounter := deadbandCounter + UDINT#1;
    END_IF;
ELSE
    deadbandCounter := UDINT#0;
END_IF;

IF (deadbandRange > REAL#0.0) AND (delayTicks > UDINT#0) AND (deadbandCounter >= delayTicks) THEN
    deadband := TRUE;
ELSE
    deadband := FALSE;
END_IF;

sleepReq := (sleepLevel > REAL#0.0)
    AND (lastPidOutput <= sleepLevel)
    AND (NOT sleepMode)
    AND (NOT sleepBoost)
    AND (NOT trackingMode);

remainingTime := sleepDelay;
delayTicks := UDINT#0;
WHILE remainingTime > T#0S DO
    delayTicks := delayTicks + UDINT#1;
    IF remainingTime > tickTime THEN
        remainingTime := remainingTime - tickTime;
    ELSE
        remainingTime := T#0S;
    END_IF;
END_WHILE;

IF sleepReq THEN
    IF clock THEN
        sleepCounter := sleepCounter + UDINT#1;
    END_IF;
ELSE
    sleepCounter := UDINT#0;
END_IF;

wakeupReq := FALSE;
IF wakeupDeviation > REAL#0.0 THEN
    wakeupReq := (deviationMagnitude >= wakeupDeviation) AND sleepMode;
END_IF;

remainingTime := wakeupDelay;
delayTicks := UDINT#0;
WHILE remainingTime > T#0S DO
    delayTicks := delayTicks + UDINT#1;
    IF remainingTime > tickTime THEN
        remainingTime := remainingTime - tickTime;
    ELSE
        remainingTime := T#0S;
    END_IF;
END_WHILE;

IF wakeupReq THEN
    IF clock THEN
        wakeupCounter := wakeupCounter + UDINT#1;
    END_IF;
ELSE
    wakeupCounter := UDINT#0;
END_IF;

IF (sleepCounter >= delayTicks) AND (sleepReq) AND (delayTicks > UDINT#0) THEN
    sleepCounter := UDINT#0;
    IF (sleepBoostLevel > REAL#0.0) AND (sleepBoostTime > T#0S) THEN
        sleepBoost := TRUE;
    ELSE
        sleepMode := TRUE;
    END_IF;
END_IF;

remainingTime := sleepBoostTime;
delayTicks := UDINT#0;
WHILE remainingTime > T#0S DO
    delayTicks := delayTicks + UDINT#1;
    IF remainingTime > tickTime THEN
        remainingTime := remainingTime - tickTime;
    ELSE
        remainingTime := T#0S;
    END_IF;
END_WHILE;

IF sleepBoost THEN
    IF clock THEN
        sleepBoostCounter := sleepBoostCounter + UDINT#1;
    END_IF;
    IF (delayTicks > UDINT#0) AND (sleepBoostCounter >= delayTicks) THEN
        sleepBoost := FALSE;
        sleepMode := TRUE;
        sleepBoostCounter := UDINT#0;
    END_IF;
ELSE
    sleepBoostCounter := UDINT#0;
END_IF;

IF (delayTicks > UDINT#0) AND (wakeupCounter >= delayTicks) AND wakeupReq THEN
    sleepMode := FALSE;
    sleepBoost := FALSE;
    wakeupCounter := UDINT#0;
    sleepCounter := UDINT#0;
END_IF;

manualMode := FALSE;
yManual := lastOutput;
tracking := FALSE;

IF trackingMode THEN
    tracking := TRUE;
    manualMode := TRUE;
    yManual := trackingRef;
ELSIF sleepBoost THEN
    manualMode := TRUE;
    yManual := sleepBoostLevel;
ELSIF sleepMode THEN
    manualMode := TRUE;
    yManual := REAL#0.0;
ELSIF deadband THEN
    manualMode := TRUE;
    yManual := lastOutput;
ELSIF outputFreezeEnable THEN
    manualMode := TRUE;
    yManual := lastOutput;
END_IF;

remainingTime := tickTime;
delayTicks := UDINT#0;
WHILE remainingTime > T#0S DO
    delayTicks := delayTicks + UDINT#1;
    IF remainingTime > T#1ms THEN
        remainingTime := remainingTime - T#1ms;
    ELSE
        remainingTime := T#0S;
    END_IF;
END_WHILE;
IF delayTicks = UDINT#0 THEN
    deltaTime := REAL#0.01;
ELSE
    deltaTime := TO_REAL(delayTicks) / REAL#1000.0;
END_IF;

rawOutput := previousOutput;
proportionalTerm := REAL#0.0;
derivativeTerm := REAL#0.0;

IF manualMode THEN
    rawOutput := yManual;
ELSE
    IF clock OR resetEdge THEN
        proportionalTerm := gain * deviationActual;

        IF integrationTime > REAL#0.0 THEN
            integralTerm := integralTerm + (gain * deviationActual * deltaTime / integrationTime);
            IF integralTerm > REAL#1000000.0 THEN
                integralTerm := REAL#1000000.0;
                overflow := TRUE;
            ELSIF integralTerm < REAL#-1000000.0 THEN
                integralTerm := REAL#-1000000.0;
                overflow := TRUE;
            END_IF;
        ELSE
            integralTerm := REAL#0.0;
        END_IF;

        IF derivationTime > REAL#0.0 THEN
            deltaDeviation := deviationActual - previousDeviation;
            derivativeTerm := gain * derivationTime * deltaDeviation / deltaTime;
        END_IF;

        rawOutput := offset + proportionalTerm + integralTerm + derivativeTerm;
        previousDeviation := deviationActual;
        previousOutput := rawOutput;
    END_IF;
END_IF;

outputLimitsActive := FALSE;
IF rawOutput < outputMin THEN
    rawOutput := outputMin;
    outputLimitsActive := TRUE;
ELSIF rawOutput > outputMax THEN
    rawOutput := outputMax;
    outputLimitsActive := TRUE;
END_IF;

outputActual := rawOutput;
lastOutput := outputActual;
lastPidOutput := outputActual;
outputFrozen := outputFreezeEnable OR deadband;

zeroOutput := FALSE;
IF outputActual < REAL#0.0 THEN
    IF -outputActual < setpointEpsilon THEN
        zeroOutput := TRUE;
    END_IF;
ELSE
    IF outputActual < setpointEpsilon THEN
        zeroOutput := TRUE;
    END_IF;
END_IF;

atSetpoint := deviationMagnitude < atSetpointHysteresis;
END_FUNCTION_BLOCK
