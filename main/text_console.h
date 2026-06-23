#ifndef TEXT_CONSOLE_H
#define TEXT_CONSOLE_H

/**
 * 文字控制台 — 通过串口收发文字消息
 *
 * 功能: 在 FreeRTOS 任务中监听 UART0 (stdin)，读取用户输入的文字，
 *       通过 Application 发送到服务器，实现无麦克风场景下的文字对话。
 *
 * 使用: 在 app_main 中调用 TextConsole::Start() 即可。
 *       串口终端输入文字 + 回车 → 发送到服务器。
 */

class TextConsole {
public:
    /**
     * 启动文字控制台任务
     * 在后台创建 FreeRTOS 任务，监听串口输入
     */
    static void Start();

private:
    static void Task(void* arg);
};

#endif // TEXT_CONSOLE_H
