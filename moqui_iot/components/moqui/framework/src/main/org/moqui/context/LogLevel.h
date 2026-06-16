#ifndef LOG_LEVEL_H
#define LOG_LEVEL_H

/* Log severity levels (faithful port of LogLevel.st). */
typedef enum {
    LOG_LEVEL_TRACE = 0,
    LOG_LEVEL_DEBUG,
    LOG_LEVEL_INFO,
    LOG_LEVEL_WARN,
    LOG_LEVEL_ERROR,
    LOG_LEVEL_FATAL,
    LOG_LEVEL_ALL,
    LOG_LEVEL_OFF
} LogLevel;

#endif /* LOG_LEVEL_H */
