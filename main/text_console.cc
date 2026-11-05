#include "text_console.h"
#include "application.h"

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <esp_rom_sys.h>
#include <cstring>
#include <cstdio>
#include <cctype>
#include <driver/uart.h>

#define TAG "TextConsole"

// SCServo 直连夹爪测试函数
static void scs_gripper(bool open) {
    uint16_t pos = open ? 2100 : 2400;  // 开/合位置（步值）

    // 只发位置包，不写速度（避免型号252控制表差异）
    uint8_t pos_pkt[9] = {0xFF, 0xFF, 6, 5, 0x03, 42,
                          (uint8_t)(pos & 0xFF), (uint8_t)((pos >> 8) & 0xFF), 0};
    uint8_t sum = 0;
    for (int i = 2; i < 8; i++) sum += pos_pkt[i];
    pos_pkt[8] = ~sum;

    uart_write_bytes(UART_NUM_1, pos_pkt, 9);
    ESP_LOGI(TAG, "SCServo 夹爪: %s → %d", open ? "张开" : "闭合", pos);
}

// SCServo 总线扫描：逐个读取舵机ID 1-6 的位置，报告在线状态
static void scs_scan() {
    printf("=== SCServo 总线扫描 ===\r\n");
    const char* names[] = {"底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"};
    int online = 0;

    for (uint8_t sid = 1; sid <= 6; sid++) {
        // 构造读位置包: {0xFF,0xFF, sid, 4, 0x02, 56, 2, cksum}
        uint8_t pkt[8] = {0xFF, 0xFF, sid, 4, 0x02, 56, 2, 0};
        uint8_t sum = 0;
        for (int i = 2; i < 7; i++) sum += pkt[i];
        pkt[7] = ~sum;

        uart_flush_input(UART_NUM_1);
        uart_write_bytes(UART_NUM_1, pkt, 8);
        esp_rom_delay_us(800);  // 等舵机响应

        uint8_t reply[8];
        int len = uart_read_bytes(UART_NUM_1, reply, 8, pdMS_TO_TICKS(20));
        if (len >= 8 && reply[0] == 0xFF && reply[1] == 0xFF && reply[2] == sid && reply[4] == 0) {
            uint16_t pos = reply[5] | ((uint16_t)reply[6] << 8);
            printf("  ID=%d (%s): ✅ 位置=%d (%.0f°)\r\n", sid, names[sid-1], pos, pos/4096.0*360.0);
            online++;
        } else {
            printf("  ID=%d (%s): ❌ 无响应\r\n", sid, names[sid-1]);
        }
    }
    printf("在线: %d/6 舵机\r\n", online);
    if (online == 0) {
        printf("⚠️ 所有舵机无响应! 检查12V电源和接线\r\n");
    }
}

void TextConsole::Start() {
    xTaskCreate(Task, "text_console", 4096, nullptr, 2, nullptr);
}

void TextConsole::Task(void* arg) {
    ESP_LOGI(TAG, "文字控制台已启动，输入文字后按回车发送（/help 帮助 /quit 退出）");

    constexpr int kMaxLine = 512;
    char buffer[kMaxLine];
    int pos = 0;

    // 打印首个提示符
    printf("\r\n> ");
    fflush(stdout);

    while (true) {
        // 逐字符读取（getchar 在 ESP32 上会阻塞等待）
        int c = getchar();
        if (c == EOF) {
            // stdin 还未就绪，稍等重试
            vTaskDelay(pdMS_TO_TICKS(200));
            continue;
        }

        if (c == '\n' || c == '\r') {
            // 换行 = 发送
            printf("\r\n");
            fflush(stdout);

            if (pos > 0) {
                buffer[pos] = '\0';

                // 特殊命令: 帮助
                if (strcmp(buffer, "/help") == 0) {
                    printf("=== 小智 AI 文字控制台 ===\r\n");
                    printf("  直接输入文字 → 发送消息给小智\r\n");
                    printf("  /help → 显示帮助\r\n");
                    printf("  /quit → 退出文字模式\r\n");
                    printf("========================\r\n");
                }
                // 特殊命令: 退出
                else if (strcmp(buffer, "/quit") == 0) {
                    ESP_LOGI(TAG, "退出文字控制台");
                    printf("已退出文字控制台。\r\n");
                }
                // SCServo 直连测试指令
                else if (strcmp(buffer, "!GOPEN") == 0) {
                    scs_gripper(true);
                    printf("GRIPPER_OPEN\r\n");
                }
                else if (strcmp(buffer, "!GCLOSE") == 0) {
                    scs_gripper(false);
                    printf("GRIPPER_CLOSE\r\n");
                }
                // 总线扫描诊断
                else if (strcmp(buffer, "!SCAN") == 0) {
                    scs_scan();
                }
                // 直连归位：所有关节回 HOME（不经过 MCP）
                else if (strcmp(buffer, "!HOME") == 0) {
                    // HOME 步值（2026-06-30 实测）
                    uint16_t home[6] = {2019, 805, 2979, 2869, 1082, 2246};
                    for (uint8_t sid = 1; sid <= 6; sid++) {
                        // 先使能扭矩
                        uint8_t torq[8] = {0xFF, 0xFF, sid, 4, 0x03, 40, 1, 0};
                        uint8_t s1 = 0;
                        for (int i = 2; i < 7; i++) s1 += torq[i];
                        torq[7] = ~s1;
                        uart_write_bytes(UART_NUM_1, torq, 8);
                        esp_rom_delay_us(200);
                        // 写目标位置
                        uint16_t pos = home[sid-1];
                        uint8_t pkt[9] = {0xFF, 0xFF, sid, 5, 0x03, 42,
                                          (uint8_t)(pos & 0xFF), (uint8_t)((pos >> 8) & 0xFF), 0};
                        uint8_t s2 = 0;
                        for (int i = 2; i < 8; i++) s2 += pkt[i];
                        pkt[8] = ~s2;
                        uart_write_bytes(UART_NUM_1, pkt, 9);
                        esp_rom_delay_us(200);
                    }
                    printf("HOME_DONE: 6关节归位\r\n");
                }
                // 手动使能全部舵机扭矩
                else if (strcmp(buffer, "!LOCK") == 0) {
                    for (uint8_t sid = 1; sid <= 6; sid++) {
                        uint8_t pkt[8] = {0xFF, 0xFF, sid, 4, 0x03, 40, 1, 0};
                        uint8_t sum = 0;
                        for (int i = 2; i < 7; i++) sum += pkt[i];
                        pkt[7] = ~sum;
                        uart_write_bytes(UART_NUM_1, pkt, 8);
                        esp_rom_delay_us(200);
                    }
                    printf("LOCK_DONE: 扭矩已使能 (ID 1-6)\r\n");
                }
                // 释放全部舵机扭矩
                else if (strcmp(buffer, "!UNLOCK") == 0) {
                    for (uint8_t sid = 1; sid <= 6; sid++) {
                        uint8_t pkt[8] = {0xFF, 0xFF, sid, 4, 0x03, 40, 0, 0};
                        uint8_t sum = 0;
                        for (int i = 2; i < 7; i++) sum += pkt[i];
                        pkt[7] = ~sum;
                        uart_write_bytes(UART_NUM_1, pkt, 8);
                        esp_rom_delay_us(200);
                    }
                    printf("UNLOCK_DONE: 扭矩已释放 (ID 1-6)\r\n");
                }
                // 串口透传：! 开头直接转发到机械臂 UART1（绕过全部链路）
                else if (buffer[0] == '!') {
                    std::string raw = std::string(buffer + 1) + "\n";
                    uart_write_bytes(UART_NUM_1, raw.c_str(), raw.size());
                    ESP_LOGI(TAG, "透传机械臂: %s", buffer + 1);
                    printf("ROBOT_OK\r\n");
                }
                // 普通文字消息
                else {
                    ESP_LOGI(TAG, "发送文字: %s", buffer);
                    Application::GetInstance().SendTextInput(std::string(buffer));
                }
                pos = 0;
            }

            // 打印新提示符
            printf("> ");
            fflush(stdout);
        }
        else if (c == '\b' || c == 127) {
            // 退格
            if (pos > 0) {
                pos--;
                printf("\b \b");
                fflush(stdout);
            }
        }
        else if (c >= 32 && c != 127) {
            // 可打印字符（接受 UTF-8 多字节编码）
            if (pos < kMaxLine - 1) {
                buffer[pos++] = (char)c;
                putchar(c);
                fflush(stdout);
            }
        }
        // 其他控制字符忽略
    }

    vTaskDelete(nullptr);
}
