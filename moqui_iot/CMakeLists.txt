cmake_minimum_required(VERSION 3.16)

# Configura IDF_PATH se non è impostato
if(NOT DEFINED ENV{IDF_PATH})
    # Prova percorsi comuni
    if(EXISTS "$ENV{HOME}/.espressif/tools/esp-idf")
        set(ENV{IDF_PATH} "$ENV{HOME}/.espressif/tools/esp-idf")
    elseif(EXISTS "/opt/esp/idf")
        set(ENV{IDF_PATH} "/opt/esp/idf")
    elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/esp-idf")
        set(ENV{IDF_PATH} "${CMAKE_CURRENT_SOURCE_DIR}/esp-idf")
    else()
        message(FATAL_ERROR 
            "IDF_PATH non è impostato e ESP-IDF non trovato nei percorsi standard.\n"
            "Per usare Docker: ./build.sh esp32\n"
            "Per installazione locale, imposta: export IDF_PATH=<percorso-esp-idf>"
        )
    endif()
endif()

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(moqui_iot_firmware)
