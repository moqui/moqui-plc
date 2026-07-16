#include "ec.h"

/* Global definition of the execution context */
ExecutionContext ec = {
    .enable = true,
    .init = true,
    .logAppenderEnable = true,
    .paramsPubEnable = false,
    .paramsSubEnable = true,
    .logSourceListSize = 0
};
