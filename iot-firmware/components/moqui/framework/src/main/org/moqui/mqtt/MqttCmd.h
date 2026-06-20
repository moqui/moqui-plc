#ifndef MQTT_CMD_H
#define MQTT_CMD_H

typedef enum {
    MQTT_CMD_IDLE = 0,
    MQTT_CMD_PUBLISH = 1,
    MQTT_CMD_SUBSCRIBE = 2,
    MQTT_CMD_UNSUBSCRIBE = 3
} MqttCmd;

#endif /* MQTT_CMD_H */
