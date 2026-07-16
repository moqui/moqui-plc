#include "ProcessPid.h"
#include "MoquiConf.h"
#include <math.h>
#include <stdio.h>

/* -------------------------------------------------------------------------
 * Simple PID core helpers (used by both Pid and ProcessPidFull)
 * ---------------------------------------------------------------------- */
static void pid_reset(Pid *p)
{
    p->integralTerm     = 0.0f;
    p->previousDeviation = 0.0f;
    p->previousOutput   = 0.0f;
}

/*
 * One-step PID update.  Parameters follow the CODESYS PID FB convention:
 *   ki = tn (integration time, seconds);  kd = tv (derivation time, seconds)
 *   yManual is the substitution output used when manual == true.
 */
static float pid_step(Pid *p,
                       float actual, float setPoint,
                       float kp, float tn, float tv,
                       float yManual, float yOffset,
                       float yMin, float yMax,
                       bool manual, bool reset,
                       bool *limitsActive, bool *overflow,
                       float dtSec)
{
    float error;
    float derivative;
    float raw;

    if (reset) { pid_reset(p); }

    if (manual) {
        p->previousOutput = yManual + yOffset;
        p->integralTerm   = 0.0f;
        return p->previousOutput;
    }

    error = setPoint - actual;

    if ((tn > 0.0f) && (dtSec > 0.0f)) {
        p->integralTerm += kp * error * (dtSec / tn);
        if (p->integralTerm > PID_INTEGRAL_SAT_LIMIT) {
            p->integralTerm = PID_INTEGRAL_SAT_LIMIT;
            *overflow = true;
        } else if (p->integralTerm < -PID_INTEGRAL_SAT_LIMIT) {
            p->integralTerm = -PID_INTEGRAL_SAT_LIMIT;
            *overflow = true;
        } else {
            *overflow = false;
        }
    } else {
        p->integralTerm = 0.0f;
    }

    derivative = 0.0f;
    if ((tv > 0.0f) && (dtSec > 0.0f)) {
        derivative = kp * tv * (error - p->previousDeviation) / dtSec;
    }
    p->previousDeviation = error;

    raw = yOffset + kp * error + p->integralTerm + derivative;

    *limitsActive = false;
    if (raw < yMin) { raw = yMin; *limitsActive = true; }
    else if (raw > yMax) { raw = yMax; *limitsActive = true; }

    p->previousOutput = raw;
    return raw;
}

/* -------------------------------------------------------------------------
 * Simple API — backward-compatible with auto-generated runtime code
 * ---------------------------------------------------------------------- */
void ProcessPid_Init(Pid *instance)
{
    instance->integralTerm     = 0.0f;
    instance->previousDeviation = 0.0f;
    instance->previousOutput   = 0.0f;
    instance->outputActual     = 0.0f;
    instance->overflow         = false;
    instance->outputLimitsActive = false;
    instance->prevReset        = false;
}

void ProcessPid_Update(Pid *instance, bool enable, bool reset,
                       bool clock, float deltaTime)
{
    if (!enable) {
        instance->outputActual     = 0.0f;
        instance->previousOutput   = 0.0f;
        instance->integralTerm     = 0.0f;
        instance->previousDeviation = 0.0f;
        return;
    }

    instance->resetEdge = (reset && !instance->prevReset);
    instance->prevReset = reset;

    if (instance->resetEdge) { pid_reset(instance); }

    if (clock || instance->resetEdge) {
        instance->outputActual = pid_step(
            instance,
            instance->feedback, instance->setpoint,
            instance->kp, instance->ki, instance->kd,
            0.0f, instance->offset,
            instance->outputMin, instance->outputMax,
            false, instance->resetEdge,
            &instance->outputLimitsActive, &instance->overflow,
            deltaTime);
    }
}

/* -------------------------------------------------------------------------
 * TON (on-delay timer)
 * ---------------------------------------------------------------------- */
static void ton_update(TonTimer *t, uint32_t tickMs)
{
    if (!t->in) {
        t->etMs = 0U;
        t->q    = false;
        return;
    }
    if (!t->q) {
        t->etMs += tickMs;
        if (t->etMs >= t->ptMs) { t->q = true; }
    }
}

/* -------------------------------------------------------------------------
 * Full API — faithful port of ProcessPid.st FUNCTION_BLOCK
 * ---------------------------------------------------------------------- */
void ProcessPidFull_Update(ProcessPid *self)
{
    float  dtSec;
    float  incSec;
    float  decSec;
    float  spRange;
    float  ascRate;
    float  decRate;
    float  expTau;
    bool   configOk;
    float  absVal;
    uint32_t tMs;

    /* Logger init */
    if (!self->loggerInit) {
        if (self->controlSystemId != NULL) {
            LoggerFacade_Init(&self->logger, self->controlSystemId);
        }
        self->loggerInit = true;
    }

    /* Master enable gate */
    if (!self->enable) {
        self->active       = false;
        self->execute      = false;
        self->outputActual = 0.0f;
        self->zeroOutput   = true;
        self->atSetpoint   = false;

        self->deadbandTimer.in   = false; ton_update(&self->deadbandTimer,   self->tickTimeMs);
        self->sleepTimer.in      = false; ton_update(&self->sleepTimer,      self->tickTimeMs);
        self->sleepBoostTimer.in = false; ton_update(&self->sleepBoostTimer, self->tickTimeMs);
        self->wakeupTimer.in     = false; ton_update(&self->wakeupTimer,     self->tickTimeMs);

        self->sleepMode  = false;
        self->sleepBoost = false;
        return;
    }

    /* Args validation */
    configOk = ((self->controlSystemId   != NULL) && (self->controlSystemId[0]   != '\0')) ||
               ((self->controlSystemName != NULL) && (self->controlSystemName[0] != '\0'));

    if (!configOk ||
        (self->integrationTime < 0.0f) || (self->derivationTime < 0.0f) ||
        (self->gain <= 0.0f) ||
        (self->setpointMin > self->setpointMax) ||
        (self->outputMin   > self->outputMax)) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_ERROR, "Invalid PID arguments.");
        self->active        = false;
        self->execute       = false;
        self->invalidConfig = true;
        return;
    }

    self->invalidConfig = false;
    self->active        = true;
    self->execute       = true;

    /* Reset edge */
    self->resetEdge = (self->reset && !self->prevReset);
    self->prevReset = self->reset;

    if (self->resetEdge) {
        LOGGER_LOG(&self->logger, LOG_LEVEL_WARN, "Reset process PID.");
        self->setpointTarget     = 0.0f;
        self->setpointInternal   = 0.0f;
        self->setpointActual     = 0.0f;
        self->lastSetpoint       = 0.0f;
        self->lastSetpointTarget = 0.0f;
        self->deviationActual    = 0.0f;
        self->outputInternal     = 0.0f;
        self->outputActual       = 0.0f;
        self->lastOutput         = 0.0f;
        self->lastPidOutput      = 0.0f;
        self->rampCurrent        = 0.0f;

        self->sShapedFunc.execute = false;
        self->expRamp.execute     = false;
        self->expRamp.reset       = true;
        SShapedFunc_Update(&self->sShapedFunc);
        IIRFilter_Update(&self->expRamp);
        self->expRamp.reset = false;

        self->deadbandTimer.in   = false; ton_update(&self->deadbandTimer,   self->tickTimeMs);
        self->sleepTimer.in      = false; ton_update(&self->sleepTimer,      self->tickTimeMs);
        self->sleepBoostTimer.in = false; ton_update(&self->sleepBoostTimer, self->tickTimeMs);
        self->wakeupTimer.in     = false; ton_update(&self->wakeupTimer,     self->tickTimeMs);

        self->sleepMode  = false;
        self->sleepBoost = false;
        pid_reset(&self->pid);
    }

    /* Feedback scaling */
    self->feedbackActual = self->feedback * self->feedbackMultiplier;

    /* Setpoint: limit + ramp + freeze */
    if (self->setpointFreezeEnable) {
        self->setpointTarget = self->lastSetpoint;
    } else {
        float sp = self->setpoint * self->setpointMultiplier;
        if (sp < self->setpointMin) { sp = self->setpointMin; }
        if (sp > self->setpointMax) { sp = self->setpointMax; }
        self->setpointTarget = sp;
    }

    dtSec = (self->tickTimeMs > 0U) ? ((float)self->tickTimeMs / 1000.0f) : 0.01f;

    if ((self->setpointIncreaseTimeMs > 0U) && (self->setpointDecreaseTimeMs > 0U)) {
        float diff = self->setpointTarget - self->lastSetpointTarget;
        if (diff < 0.0f) { diff = -diff; }
        self->startRamp          = (diff > self->setpointEpsilon) || self->resetEdge;
        self->lastSetpointTarget = self->setpointTarget;

        switch (self->setpointRampType) {
            case RAMP_TYPE_S_SHAPED:
                self->sShapedFunc.execute    = (self->startRamp || self->sShapedFunc.busy);
                self->sShapedFunc.clock      = self->clock;
                self->sShapedFunc.startValue = self->lastSetpoint;
                self->sShapedFunc.endValue   = self->setpointTarget;
                self->sShapedFunc.durationMs =
                    (self->setpointTarget >= self->lastSetpoint)
                    ? self->setpointIncreaseTimeMs
                    : self->setpointDecreaseTimeMs;
                self->sShapedFunc.tickTimeMs = self->tickTimeMs;
                SShapedFunc_Update(&self->sShapedFunc);
                self->setpointInternal = self->sShapedFunc.error
                                         ? self->setpointTarget
                                         : self->sShapedFunc.output;
                break;

            case RAMP_TYPE_LINEAR:
                if (self->clock || self->resetEdge) {
                    incSec  = (float)self->setpointIncreaseTimeMs / 1000.0f;
                    decSec  = (float)self->setpointDecreaseTimeMs / 1000.0f;
                    if (incSec < 0.001f) { incSec = 0.001f; }
                    if (decSec < 0.001f) { decSec = 0.001f; }
                    spRange = self->setpointMax - self->setpointMin;
                    if (spRange < 1.0f) { spRange = 1.0f; }
                    ascRate = spRange / incSec;
                    decRate = spRange / decSec;

                    if (self->startRamp) { self->rampCurrent = self->lastSetpoint; }

                    if (self->rampCurrent < self->setpointTarget) {
                        self->rampCurrent += ascRate * dtSec;
                        if (self->rampCurrent > self->setpointTarget) { self->rampCurrent = self->setpointTarget; }
                    } else if (self->rampCurrent > self->setpointTarget) {
                        self->rampCurrent -= decRate * dtSec;
                        if (self->rampCurrent < self->setpointTarget) { self->rampCurrent = self->setpointTarget; }
                    } else {
                        /* at target */
                    }
                    self->setpointInternal = self->rampCurrent;
                }
                break;

            case RAMP_TYPE_EXPONENTIAL:
                tMs    = (self->setpointTarget >= self->lastSetpoint)
                         ? self->setpointIncreaseTimeMs
                         : self->setpointDecreaseTimeMs;
                expTau = (float)tMs / 4605.0f;
                if (expTau < 0.001f) { expTau = 0.001f; }
                self->expRamp.execute    = true;
                self->expRamp.clock      = self->clock;
                self->expRamp.reset      = self->startRamp;
                self->expRamp.input      = self->setpointTarget;
                self->expRamp.T          = expTau;
                self->expRamp.tickTimeMs = self->tickTimeMs;
                IIRFilter_Update(&self->expRamp);
                self->setpointInternal = self->expRamp.error
                                         ? self->setpointTarget
                                         : self->expRamp.output;
                break;

            default:
                self->setpointInternal = self->setpointTarget;
                break;
        }
        self->lastSetpoint = self->setpointInternal;
    } else {
        self->setpointInternal   = self->setpointTarget;
        self->lastSetpoint       = self->setpointInternal;
        self->lastSetpointTarget = self->setpointTarget;
    }

    self->setpointFrozen = self->setpointFreezeEnable;
    self->setpointActual = self->setpointInternal;

    /* Deviation */
    if (!self->deviationInversion) {
        self->deviationActual = self->setpointActual - self->feedbackActual;
    } else {
        self->deviationActual = self->feedbackActual - self->setpointActual;
    }

    /* Deadband */
    absVal = self->deviationActual;
    if (absVal < 0.0f) { absVal = -absVal; }
    self->deadbandTimer.in  = (self->deadbandRange > 0.0f) && (absVal <= self->deadbandRange);
    self->deadbandTimer.ptMs = self->deadbandDelayMs;
    if (self->clock) { ton_update(&self->deadbandTimer, self->tickTimeMs); }
    self->deadband = self->deadbandTimer.q;

    /* Sleep / wake-up */
    self->sleepReq = (self->sleepLevel > 0.0f) &&
                     (self->lastPidOutput <= self->sleepLevel) &&
                     !self->sleepMode && !self->sleepBoost && !self->trackingMode;
    self->sleepTimer.in   = self->sleepReq;
    self->sleepTimer.ptMs = self->sleepDelayMs;
    if (self->clock) { ton_update(&self->sleepTimer, self->tickTimeMs); }

    absVal = self->deviationActual;
    if (absVal < 0.0f) { absVal = -absVal; }
    self->wakeupReq = (self->wakeupDeviation > 0.0f) && (absVal >= self->wakeupDeviation) && self->sleepMode;
    self->wakeupTimer.in   = self->wakeupReq;
    self->wakeupTimer.ptMs = self->wakeupDelayMs;
    if (self->clock) { ton_update(&self->wakeupTimer, self->tickTimeMs); }

    if (self->sleepTimer.q) {
        self->sleepTimer.in = false; ton_update(&self->sleepTimer, self->tickTimeMs);
        if ((self->sleepBoostLevel > 0.0f) && (self->sleepBoostTimeMs > 0U)) {
            self->sleepBoost = true;
        } else {
            self->sleepMode = true;
        }
    }

    self->sleepBoostTimer.in   = self->sleepBoost;
    self->sleepBoostTimer.ptMs = self->sleepBoostTimeMs;
    if (self->clock) { ton_update(&self->sleepBoostTimer, self->tickTimeMs); }
    if (self->sleepBoostTimer.q) {
        self->sleepBoost = false;
        self->sleepBoostTimer.in = false; ton_update(&self->sleepBoostTimer, self->tickTimeMs);
        self->sleepMode = true;
    }

    if (self->wakeupTimer.q) {
        self->sleepMode = false;
        self->sleepTimer.in = false; ton_update(&self->sleepTimer, self->tickTimeMs);
    }

    /* Control mode priority */
    self->tracking   = false;
    self->manualMode = false;
    self->yManual    = self->lastOutput;

    if (self->trackingMode) {
        self->tracking   = true;
        self->manualMode = true;
        self->yManual    = self->trackingRef;
        self->sleepTimer.in = false; ton_update(&self->sleepTimer, self->tickTimeMs);
        self->sleepBoost = false;
        self->sleepBoostTimer.in = false; ton_update(&self->sleepBoostTimer, self->tickTimeMs);
    } else if (self->sleepBoost) {
        self->manualMode = true;
        self->yManual    = self->sleepBoostLevel;
    } else if (self->sleepMode) {
        self->manualMode = true;
        self->yManual    = 0.0f;
    } else if (self->deadband) {
        self->manualMode = true;
        self->yManual    = self->lastOutput;
    } else {
        self->manualMode = self->outputFreezeEnable;
        self->yManual    = self->lastOutput;
    }

    /* Core PID */
    if (self->clock || self->resetEdge) {
        self->overflow = false;
        self->outputInternal = pid_step(
            &self->pid,
            self->feedbackActual, self->setpointActual,
            self->gain, self->integrationTime, self->derivationTime,
            self->yManual, self->offset,
            self->outputMin, self->outputMax,
            self->manualMode, self->resetEdge,
            &self->outputLimitsActive, &self->overflow,
            dtSec);
    }

    self->lastPidOutput = self->outputInternal;
    self->outputActual  = self->outputInternal;
    self->outputFrozen  = self->outputFreezeEnable || self->deadband;

    absVal = self->outputActual;
    if (absVal < 0.0f) { absVal = -absVal; }
    self->zeroOutput = (absVal < self->setpointEpsilon);
    self->lastOutput = self->outputActual;

    absVal = self->deviationActual;
    if (absVal < 0.0f) { absVal = -absVal; }
    self->atSetpoint = (absVal < self->atSetpointHysteresis);
}
