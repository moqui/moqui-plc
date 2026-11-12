#include "HvacDeviceConfigOps.h"
#include "RecipeManagerCmds.h"
#include "DeviceConfigLoader.h"
#include <string.h>

/* Known embedded recipe names (matches EMBED_TXTFILES in CMakeLists.txt) */
static const char * const s_recipes[] = {
    "Phase1HvacCooling",
    "Phase2HvacDrying",
    "Phase3HvacHeating",
    "Phase4HvacDrying_Progressive",
    "Phase5HvacDrying_Intensive",
};
#define RECIPE_COUNT ((uint16_t)(sizeof(s_recipes) / sizeof(s_recipes[0])))

/* RecipeManagerCmds instance hidden inside this ops implementation */
static RecipeManagerCmds s_recipe_mgr;

/* loadFn registered on RecipeManagerCmds — calls DeviceConfigLoader */
static bool hvac_load_fn(const char *name, void *ctx) {
    return DeviceConfigLoader_Load(name, (DeviceFacade *)ctx);
}

/* ---------------------------------------------------------------------- */

static uint32_t list_configs(void *ctx, const char *path, const char *type,
                              char names[][64], uint16_t max, uint16_t *count) {
    (void)ctx; (void)path; (void)type;
    uint16_t n = (max < RECIPE_COUNT) ? max : RECIPE_COUNT;
    if (n != RECIPE_COUNT) { *count = 0U; return 1U; }
    for (uint16_t i = 0U; i < n; i++) {
        strncpy(names[i], s_recipes[i], 63U);
        names[i][63] = '\0';
    }
    *count = n;
    return 0U;
}

static uint32_t load_config(void *ctx, const char *path, const char *type, const char *name) {
    (void)path; (void)type;
    /* Wire RecipeManagerCmds with the HVAC loader and trigger it */
    s_recipe_mgr.recipeName = name;
    s_recipe_mgr.loadFn     = hvac_load_fn;
    s_recipe_mgr.loadCtx    = ctx; /* DeviceFacade * */
    s_recipe_mgr.execute    = true;
    s_recipe_mgr.done       = false; /* Reset done gate */
    RecipeManagerCmds_Update(&s_recipe_mgr);
    s_recipe_mgr.execute    = false;
    return s_recipe_mgr.error ? 1U : 0U;
}

/* ---------------------------------------------------------------------- */

void HvacDeviceConfigOps_Init(DeviceConfigOps *ops, DeviceFacade *dev) {
    ops->context      = dev;
    ops->listConfigs  = list_configs;
    ops->loadConfig   = load_config;
    ops->createConfig = NULL; /* embedded recipes are read-only */
    ops->saveConfig   = NULL;
    ops->deleteConfig = NULL;
}
