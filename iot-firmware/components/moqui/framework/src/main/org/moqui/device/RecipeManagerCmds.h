#ifndef RECIPE_MANAGER_CMDS_H
#define RECIPE_MANAGER_CMDS_H

#include <stdint.h>
#include <stdbool.h>
#include "LoggerFacade.h"

typedef struct {
    /* VAR_INPUT */
    bool execute;
    const char *recipeName;

    /* VAR_EXTERNAL — set by application to provide the actual recipe loading. */
    bool (*loadFn)(const char *recipeName, void *ctx);
    void *loadCtx;

    /* VAR_OUTPUT */
    bool done;
    bool busy;
    bool error;

    /* VAR */
    LoggerFacade logger;
    bool init;
    bool prevExecute;

} RecipeManagerCmds;

void RecipeManagerCmds_Update(RecipeManagerCmds *cmds);

#endif /* RECIPE_MANAGER_CMDS_H */
