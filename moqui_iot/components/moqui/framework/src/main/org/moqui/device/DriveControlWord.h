#ifndef DRIVE_CONTROL_WORD_H
#define DRIVE_CONTROL_WORD_H

/*
 * Drive control words for start, stop and reset commands
 * (faithful port of DriveControlWord.st).
 */
typedef enum {
    /* ABB ACS580, ACH580 drive */
    DRIVE_CTRL_ABBACH580_RESET = 1278,
    DRIVE_CTRL_ABBACH580_STOP  = 1150,
    DRIVE_CTRL_ABBACH580_START = 1151,
    /* Control Techniques M600 drive */
    DRIVE_CTRL_CTM600_RESET = 111,
    DRIVE_CTRL_CTM600_STOP  = 112,
    DRIVE_CTRL_CTM600_START = 113,
    /* Danfoss FC102 drive */
    DRIVE_CTRL_DANFOSS_FC102_RESET = 121,
    DRIVE_CTRL_DANFOSS_FC102_STOP  = 122,
    DRIVE_CTRL_DANFOSS_FC102_START = 123
} DriveControlWord;

#endif /* DRIVE_CONTROL_WORD_H */
