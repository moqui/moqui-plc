#ifndef HOST_QUEUE_H
#define HOST_QUEUE_H
#include "FreeRTOS.h"
QueueHandle_t xQueueCreateStatic(unsigned count, unsigned size, uint8_t *data, StaticQueue_t *queue);
int xQueueSend(QueueHandle_t queue, const void *data, TickType_t wait);
int xQueueReceive(QueueHandle_t queue, void *data, TickType_t wait);
#endif
