#include "platform.h"
#include "esp_timer.h"

uint64_t pal_time_us(void) {
    return (uint64_t)esp_timer_get_time();
}
