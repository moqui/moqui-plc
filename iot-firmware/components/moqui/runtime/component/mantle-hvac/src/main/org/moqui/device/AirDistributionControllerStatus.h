#ifndef AIR_DISTRIBUTION_CONTROLLER_STATUS_H
#define AIR_DISTRIBUTION_CONTROLLER_STATUS_H

/*
 * AirDistributionControllerStatus — port of AirDistributionControllerStatus.st
 */
typedef enum {
    AIR_DIST_STATUS_INIT               = 0,
    AIR_DIST_STATUS_HIGH_PHASE         = 1,
    AIR_DIST_STATUS_TRANSITION_TO_LOW  = 2,
    AIR_DIST_STATUS_LOW_PHASE          = 3,
    AIR_DIST_STATUS_TRANSITION_TO_HIGH = 4
} AirDistributionControllerStatus;

#endif /* AIR_DISTRIBUTION_CONTROLLER_STATUS_H */
