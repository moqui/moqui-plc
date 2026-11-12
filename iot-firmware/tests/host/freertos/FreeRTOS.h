#ifndef HOST_FREERTOS_H
#define HOST_FREERTOS_H
#include <assert.h>
#include <stdint.h>
#include <pthread.h>
typedef uint32_t TickType_t;
typedef uint32_t StackType_t;
typedef int StaticTask_t;
typedef struct {
    pthread_mutex_t mutex;
    uint8_t *data;
    unsigned capacity, size, head, count;
} StaticQueue_t;
typedef StaticQueue_t *QueueHandle_t;
#define pdTRUE 1
#define pdFALSE 0
#define pdMS_TO_TICKS(ms) (ms)
#define configMAX_PRIORITIES 25
#define configASSERT(x) assert(x)
#define portMAX_DELAY UINT32_MAX
#endif
