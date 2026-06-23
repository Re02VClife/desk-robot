#include "text_console.h"
#include "application.h"

#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <esp_log.h>
#include <cstring>
#include <cstdio>
#include <cctype>

#define TAG "TextConsole"

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
        else if (c >= 32 && c < 127) {
            // 可打印字符
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
