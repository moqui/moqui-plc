#ifndef HOST_TASK_H
#define HOST_TASK_H
#include "FreeRTOS.h"
TickType_t xTaskGetTickCount(void);
void vTaskDelayUntil(TickType_t *wake, TickType_t period);
void vTaskDelay(TickType_t period);
void vTaskSuspend(void *task);
void *xTaskCreateStaticPinnedToCore(void (*run)(void *), const char *name,
    uint32_t depth, void *arg, unsigned priority, StackType_t *stack,
    StaticTask_t *buffer, int core);
#define taskYIELD() ((void)0)
#endif
