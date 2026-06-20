#ifndef LOG_CMD_H
#define LOG_CMD_H

typedef enum {
    LOG_CMD_IDLE = 0,
    LOG_CMD_PUSH = 1,
    LOG_CMD_INCREMENT_LAST = 2,
    LOG_CMD_PEEK = 3,
    LOG_CMD_POP = 4,
    LOG_CMD_CLEAR = 5
} LogCmd;

#endif /* LOG_CMD_H */
