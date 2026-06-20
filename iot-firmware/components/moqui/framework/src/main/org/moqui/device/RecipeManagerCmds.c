#include "RecipeManagerCmds.h"

void RecipeManagerCmds_Update(RecipeManagerCmds *cmds) {
    if (!cmds->init) {
        cmds->logger.enable = true;
        cmds->logger.loggerName = "RecipeManager";
        cmds->init = true;
    }

    if (!cmds->execute) {
        cmds->done = false;
        cmds->busy = false;
        cmds->error = false;
        return;
    }

    if (cmds->done) return; /* Already completed this execute pulse */

    cmds->busy = true;
    LOGGER_LOG(&cmds->logger, LOG_LEVEL_DEBUG, "Loading recipe: %s",
               cmds->recipeName ? cmds->recipeName : "(null)");

    if (cmds->loadFn) {
        bool ok = cmds->loadFn(cmds->recipeName, cmds->loadCtx);
        cmds->done  = ok;
        cmds->error = !ok;
    } else {
        /* No loader — succeed silently (simulation / test mode) */
        cmds->done = true;
    }
    cmds->busy = false;
}
