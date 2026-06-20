#include "DeviceManager.h"

void DeviceManager_Update(DeviceFacade *dev, const Clocks *clks, OperatingMode operationType) {
    
    /* Cold glycol group */
    dev->coldGlycolPump.operationType = operationType;
    dev->coldGlycolPump.clock = clks->clock100ms;
    dev->coldGlycolPump.enableRequest = &dev->coldGroupEnableRequest;
    dev->coldGlycolPump.disableRequest = &dev->coldGroupDisableRequest;
    Actuator_Update(&dev->coldGlycolPump);

    dev->coldGlycolValve.feedback    = dev->tempFeedback;
    dev->coldGlycolValve.setpoint    = dev->tempSetpoint;
    dev->coldGlycolValve.enable      = dev->coldGroupEnableRequest;
    dev->coldGlycolValve.reset       = false;
    dev->coldGlycolValve.clock       = clks->clock100ms;
    dev->coldGlycolValve.tickTimeMs  = 100U;
    ProcessPidFull_Update(&dev->coldGlycolValve);

    /* Hot glycol group */
    dev->hotGlycolPump.operationType = operationType;
    dev->hotGlycolPump.clock = clks->clock100ms;
    dev->hotGlycolPump.enableRequest = &dev->hotGroupEnableRequest;
    dev->hotGlycolPump.disableRequest = &dev->hotGroupDisableRequest;
    Actuator_Update(&dev->hotGlycolPump);

    dev->hotGlycolValve.feedback    = dev->tempFeedback;
    dev->hotGlycolValve.setpoint    = dev->tempSetpoint;
    dev->hotGlycolValve.enable      = dev->hotGroupEnableRequest;
    dev->hotGlycolValve.reset       = false;
    dev->hotGlycolValve.clock       = clks->clock100ms;
    dev->hotGlycolValve.tickTimeMs  = 100U;
    ProcessPidFull_Update(&dev->hotGlycolValve);

    /* AHU fan */
    dev->ahuFan.setpoint   = dev->ahuFanSpeedSetpoint;
    dev->ahuFan.feedback   = dev->ahuFanSpeedFeedback;
    dev->ahuFan.enable     = dev->ahuFanEnableRequest;
    dev->ahuFan.reset      = false;
    dev->ahuFan.clock      = clks->clock100ms;
    dev->ahuFan.tickTimeMs = 100U;
    ProcessPidFull_Update(&dev->ahuFan);

    /* Air flow distributor */
    dev->airFlow.operationType = operationType;
    dev->airFlow.clock = clks->clock100ms;
    dev->airFlow.ref = dev->airFlowRef;
    dev->airFlow.feedback = dev->airFlowSpeedFeedback;
    dev->airFlow.enableRequest = &dev->airFlowEnableRequest;
    dev->airFlow.disableRequest = &dev->airFlowDisableRequest;
    Actuator_Update(&dev->airFlow);

    /* High flow damper */
    dev->highFlowDamper.operationType = operationType;
    dev->highFlowDamper.clock = clks->clock100ms;
    dev->highFlowDamper.enableRequest = &dev->highFlowDamperEnableRequest;
    dev->highFlowDamper.disableRequest = &dev->highFlowDamperDisableRequest;
    Actuator_Update(&dev->highFlowDamper);

    /* Low flow damper */
    dev->lowFlowDamper.operationType = operationType;
    dev->lowFlowDamper.clock = clks->clock100ms;
    dev->lowFlowDamper.enableRequest = &dev->lowFlowDamperEnableRequest;
    dev->lowFlowDamper.disableRequest = &dev->lowFlowDamperDisableRequest;
    Actuator_Update(&dev->lowFlowDamper);

    /* Air mixing fan — FB wired to the bool request fields */
    dev->airMixingFan.operationType = operationType;
    dev->airMixingFan.clock = clks->clock100ms;
    dev->airMixingFan.enableRequest  = &dev->airMixingFanEnableRequest;
    dev->airMixingFan.disableRequest = &dev->airMixingFanDisableRequest;
    if (dev->airMixingEnabled) {
        dev->airMixingFanEnableRequest = true;
    } else {
        dev->airMixingFanDisableRequest = true;
    }
    Actuator_Update(&dev->airMixingFan);
}
