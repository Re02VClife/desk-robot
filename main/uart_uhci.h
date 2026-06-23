// uart_uhci.h — ESP-IDF v5.5 兼容性桩头文件
//
// ESP-IDF v5.5 移除了 uart_uhci 组件（UART UHCI DMA 驱动）。
// 78__esp-ml307 组件依赖此头文件用于 4G 模组 AT 通信。
// 此桩文件提供最小类型定义以通过编译，但不提供实际 DMA 功能。
//
// 注意：ESP-IDF v5.5 上 4G 模组（ML307/NT26）板子无法正常工作。
//       仅用于使非模组板子（如 XIAOZHI_CUSTOM）能够通过编译。
#pragma once

#include <cstdint>
#include <cstddef>
#include <esp_err.h>

class UartUhci {
public:
    struct RxBuffer {
        // 桩类型：仅用于编译，无实际成员
    };

    struct RxEventData {
        RxBuffer* buffer = nullptr;
        size_t recv_size = 0;
    };

    struct RxPoolConfig {
        size_t buffer_count = 0;
        size_t buffer_size = 0;
    };

    struct Config {
        int uart_port = 0;
        int dma_burst_size = 0;
        RxPoolConfig rx_pool = {};
    };

    using RxCallback = bool (*)(const RxEventData& data, void* user_data);
    using OverflowCallback = bool (*)(void* user_data);

    esp_err_t Init(const Config& config) { return ESP_FAIL; }
    void Deinit() {}
    esp_err_t StartReceive() { return ESP_FAIL; }
    void SetRxCallback(RxCallback callback, void* user_data) {}
    void SetOverflowCallback(OverflowCallback callback, void* user_data) {}
    void ReturnBuffer(RxBuffer* buffer) {}
    esp_err_t Transmit(const uint8_t* data, size_t length) { return ESP_FAIL; }
};
