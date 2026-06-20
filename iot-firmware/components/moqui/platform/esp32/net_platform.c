#include "platform.h"
#include "esp_netif.h"
#include "esp_mac.h"
#include "esp_event.h"
#include "nvs_flash.h"
#include "esp_err.h"
#include <stdio.h>

void pal_hardware_init(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
}

bool pal_net_is_connected(void) {
    esp_netif_t *netif = esp_netif_get_default_netif();
    return (netif != NULL) && esp_netif_is_netif_up(netif);
}

void pal_net_get_mac_str(char *out, size_t max) {
    uint8_t mac[6];
    esp_read_mac(mac, ESP_MAC_BASE);
    snprintf(out, max, "%02x%02x%02x%02x%02x%02x",
             mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}
