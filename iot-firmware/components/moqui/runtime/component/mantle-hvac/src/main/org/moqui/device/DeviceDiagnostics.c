#include "DeviceDiagnostics.h"
#include "SignalMgmt.h"
#include "SignalCategory.h"
#include "ResetPolicy.h"
#include "SignalOutputAction.h"
#include "SignalMgmtOperatingMode.h"

/*
 * Faithful port of DeviceDiagnostics.st.
 *
 * Signal management cycle (mirrors ST named-parameter calls):
 *   1. Prepare  — clears cumulativeOutputAction
 *   2. Process  — one call per signal, in priority order
 *
 * After this function returns, dev->signalMgmt.cumulativeOutputAction
 * contains the OR of all active signal output actions for this scan.
 */

/* Helper: configure all SignalMgmt fields for one signal and run one Process tick. */
static void process_signal(SignalMgmt *sm,
                            const char *loggerName,
                            uint16_t    code,
                            SignalCategory     category,
                            ResetPolicy        resetPol,
                            bool               activationCondition,
                            SignalOutputAction outputAction) {
    sm->loggerName          = loggerName;
    sm->code                = code;
    sm->category            = category;
    sm->resetPol            = resetPol;
    sm->activationCondition = activationCondition;
    sm->outputAction        = outputAction;
    SignalMgmt_Update(sm);
}

void DeviceDiagnostics_Update(DeviceDiagnostics *diags, DeviceFacade *dev) {
    (void)diags;

    diags->error = true;

    /* ---- Prepare cycle: clear accumulated output action ---- */
    dev->signalMgmt.operationType = SIGNAL_MGMT_OPERATING_MODE_PREPARE;
    SignalMgmt_Update(&dev->signalMgmt);

    dev->signalMgmt.operationType = SIGNAL_MGMT_OPERATING_MODE_PROCESS;

    /* ---- Device fault signals (ImmediateStop priority) ---- */
    process_signal(&dev->signalMgmt,
        dev->ahuFan.loggerName,
        0x0001U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->ahuFan.invalidConfig,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->airFlow.loggerName,
        0x0002U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->airFlow.fault,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->coldGlycolPump.loggerName,
        0x0003U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->coldGlycolPump.fault,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->coldGlycolValve.loggerName,
        0x0004U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->coldGlycolValve.invalidConfig,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->hotGlycolPump.loggerName,
        0x0005U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->hotGlycolPump.fault,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->hotGlycolValve.loggerName,
        0x0006U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->hotGlycolValve.invalidConfig,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->highFlowDamper.loggerName,
        0x0007U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->highFlowDamper.fault,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    process_signal(&dev->signalMgmt,
        dev->lowFlowDamper.loggerName,
        0x0008U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->lowFlowDamper.fault,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    /* Air mixing fan — optional, activated only when airMixingEnabled */
    if (dev->airMixingEnabled) {
        process_signal(&dev->signalMgmt,
            dev->airMixingFan.loggerName,
            0x0009U,
            SIGNAL_CATEGORY_ALARM,
            RESET_POLICY_UNCONDITIONED_RESET,
            dev->airMixingFan.fault,
            SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);
    }

    /* ---- Duct safety alarms ---- */

    /* Supply-air over-temperature: ImmediateStop — product damage risk */
    process_signal(&dev->signalMgmt,
        MOQUI_APPLICATION_DEVICE_ID,
        0x0010U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->ductTempOverMax,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    /* Supply-air under-temperature: ImmediateStop — contamination risk */
    process_signal(&dev->signalMgmt,
        MOQUI_APPLICATION_DEVICE_ID,
        0x0011U,
        SIGNAL_CATEGORY_ALARM,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->ductTempUnderMin,
        SIGNAL_OUTPUT_ACTION_IMMEDIATE_STOP);

    /* Duct RH over-max: Warning only — condensation risk, no machine stop */
    process_signal(&dev->signalMgmt,
        MOQUI_APPLICATION_DEVICE_ID,
        0x0012U,
        SIGNAL_CATEGORY_WARNING,
        RESET_POLICY_UNCONDITIONED_RESET,
        dev->ductRhOverMax,
        SIGNAL_OUTPUT_ACTION_NONE);

    diags->error = false;
}
