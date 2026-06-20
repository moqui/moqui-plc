#include "ec.h"

/* Global definition of the execution context */
ExecutionContext ec = {
    .enable = true,
    .init = true,
    .logAppenderEnable = true,
    .paramsPubEnable = true,
    .paramsSubEnable = true,
    .logSourceListSize = 0
};
