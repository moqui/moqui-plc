#ifndef PROCESS_PID_H
#define PROCESS_PID_H

#include <stdint.h>
#include <stdbool.h>
#include "RampType.h"
#include "IIRFilter.h"
#include "SShapedFunc.h"
#include "LoggerFacade.h"

/*
 * Pid — simple core PID struct.
 * Used by auto-generated runtime code (DeviceFacade, DeviceManager).
 * Maps to the inner pid : PID block referenced by ProcessPid.st.
 */
typedef struct {
    /* Parameters */
    float kp;    /* Proportional gain */
    float ki;    /* Integration time (tn), seconds. 0 = disabled */
    float kd;    /* Derivation time (tv), seconds. 0 = disabled */
    float offset;
    float setpoint;
    float feedback;

    /* Output limits */
    float outputMin;
    float outputMax;

    /* Internal state */
    float integralTerm;
    float previousDeviation;
    float previousOutput;

    /* Outputs */
    float outputActual;
    bool  overflow;
    bool  outputLimitsActive;

    /* Edge detection */
    bool resetEdge;
    bool prevReset;

} Pid;

void ProcessPid_Init(Pid *instance);
void ProcessPid_Update(Pid *instance, bool enable, bool reset, bool clock, float deltaTime);

/* -------------------------------------------------------------------------
 * ProcessPid — full faithful port of ProcessPid.st FUNCTION_BLOCK.
 * Use ProcessPidFull_Update() for this variant.
 * ---------------------------------------------------------------------- */

/* Simple on-delay timer (port of TON function block) */
typedef struct {
    bool     in;
    uint32_t ptMs;
    uint32_t etMs;
    bool     q;
} TonTimer;

typedef struct {
    /* VAR_INPUT */
    bool         enable;
    bool         reset;
    const char  *controlSystemId;
    const char  *controlSystemName;

    float feedback;
    float feedbackMultiplier;    /* Default 1.0 */
    float setpoint;
    float atSetpointHysteresis;

    float setpointMultiplier;    /* Default 1.0 */
    float setpointMin;
    float setpointMax;

    RampType setpointRampType;
    uint32_t setpointIncreaseTimeMs;
    uint32_t setpointDecreaseTimeMs;
    bool     setpointFreezeEnable;
    bool     deviationInversion;

    float outputMin;
    float outputMax;
    bool  outputFreezeEnable;

    float gain;             /* kp. Default 1.0 */
    float integrationTime;  /* tn seconds. 0 = disabled */
    float derivationTime;   /* tv seconds. 0 = disabled */
    float offset;

    float    deadbandRange;
    uint32_t deadbandDelayMs;

    float    sleepLevel;    /* 0.0 = disabled */
    uint32_t sleepDelayMs;
    float    wakeupDeviation;
    uint32_t wakeupDelayMs;
    float    sleepBoostLevel;
    uint32_t sleepBoostTimeMs;

    bool  trackingMode;
    float trackingRef;

    bool     clock;
    uint32_t tickTimeMs;
    float    setpointEpsilon; /* Default 0.000001 */

    /* VAR_OUTPUT */
    float feedbackActual;
    float setpointActual;
    float deviationActual;
    float outputActual;

    bool  invalidConfig;
    bool  active;
    bool  atSetpoint;
    bool  zeroOutput;
    bool  setpointFrozen;
    bool  outputFrozen;
    bool  sleepMode;
    bool  sleepBoost;
    bool  deadband;
    bool  tracking;
    bool  outputLimitsActive;
    bool  overflow;

    const char *loggerName;

    /* VAR */
    Pid      pid;
    TonTimer deadbandTimer;
    TonTimer sleepTimer;
    TonTimer sleepBoostTimer;
    TonTimer wakeupTimer;

    float setpointTarget;
    float setpointInternal;
    float lastSetpoint;
    float lastSetpointTarget;
    float outputInternal;
    float lastOutput;
    float lastPidOutput;

    bool  execute;
    bool  manualMode;
    float yManual;
    bool  sleepReq;
    bool  wakeupReq;
    bool  prevReset;
    bool  resetEdge;
    bool  startRamp;

    float rampCurrent;

    SShapedFunc sShapedFunc;
    IIRFilter   expRamp;

    char         loggerNameBuf[64];
    LoggerFacade logger;
    bool         loggerInit;

} ProcessPid;

void ProcessPidFull_Update(ProcessPid *self);

#endif /* PROCESS_PID_H */
