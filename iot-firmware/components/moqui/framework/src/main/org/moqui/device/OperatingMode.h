#ifndef OPERATING_MODE_H
#define OPERATING_MODE_H

/*
 * Function block operating mode (faithful port of OperatingMode.st).
 * Init := 1 matches the ST definition exactly so serialized values are interoperable.
 */
typedef enum {
    OPERATING_MODE_INIT = 1,
    OPERATING_MODE_RUN  = 2
} OperatingMode;

#endif /* OPERATING_MODE_H */
