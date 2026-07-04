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
    uint16_t speed = 150;

    // 速度包: [0xFF,0xFF, ID, Len, WRITE, Addr, ValL, ValH, Cksum]
    uint8_t spd[9] = {0xFF, 0xFF, 6, 5, 0x03, 46,
                      (uint8_t)(speed & 0xFF), (uint8_t)((speed >> 8) & 0xFF), 0};
    uint8_t sum = 0;
    for (int i = 2; i < 8; i++) sum += spd[i];
    spd[8] = ~sum;

    // 位置包
    uint8_t pos_pkt[9] = {0xFF, 0xFF, 6, 5, 0x03, 42,
                          (uint8_t)(pos & 0xFF), (uint8_t)((pos >> 8) & 0xFF), 0};
    sum = 0;
    for (int i = 2; i < 8; i++) sum += pos_pkt[i];
    pos_pkt[8] = ~sum;

    uart_write_bytes(UART_NUM_1, spd, 9);
    esp_rom_delay_us(300);
    uart_write_bytes(UART_NUM_1, pos_pkt, 9);
    ESP_LOGI(TAG, "SCServo 夹爪: %s → %d", open ? "张开" : "闭合", pos);
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
