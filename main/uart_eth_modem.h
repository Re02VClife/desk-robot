// uart_eth_modem.h — ESP-IDF v5.5 兼容性桩头文件
//
// ESP-IDF v5.5 移除了 esp_eth_modem 组件。
// NT26 4G 模组依赖此组件。此桩文件提供最小类型定义以通过编译。
//
// 注意：ESP-IDF v5.5 上 NT26 板子无法正常工作。
//       仅用于使非模组板子（如 XIAOZHI_CUSTOM）能够通过编译。
#pragma once

#include <cstdint>
#include <string>
#include <functional>
#include <memory>
#include <esp_err.h>
#include <driver/gpio.h>
#include <driver/uart.h>

class UartEthModem {
public:
    struct Config {
        uart_port_t uart_num = UART_NUM_1;
        int baud_rate = 3000000;
        gpio_num_t tx_pin = GPIO_NUM_NC;
        gpio_num_t rx_pin = GPIO_NUM_NC;
        gpio_num_t mrdy_pin = GPIO_NUM_NC;
        gpio_num_t srdy_pin = GPIO_NUM_NC;
        gpio_num_t reset_pin = GPIO_NUM_NC;
    };

    enum class UartEthModemEvent {
        Connected,
        Disconnected,
        ErrorNoSim,
        ErrorRegistrationDenied,
        Connecting,
        ErrorInitFailed,
        ErrorNoCarrier,
        InFlightMode
    };

    struct CellInfo {
        int stat = 0;
        std::string tac;
        std::string ci;
        int act = -1;
    };

    using NetworkEventCallback = std::function<void(UartEthModemEvent)>;

    explicit UartEthModem(const Config& config) {}
    ~UartEthModem() = default;

    esp_err_t Start() { return ESP_FAIL; }
    void Stop() {}
    void SetDebug(bool enable) {}
    void SetNetworkEventCallback(NetworkEventCallback callback) {}
    bool IsInitialized() const { return false; }
    int GetSignalStrength() const { return -1; }
    std::string GetModuleRevision() const { return ""; }
    std::string GetCarrierName() const { return ""; }
    std::string GetImei() const { return ""; }
    std::string GetIccid() const { return ""; }
    CellInfo GetCellInfo() const { return {}; }
};
