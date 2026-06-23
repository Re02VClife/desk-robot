#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/lcd_display.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "led/single_led.h"
#include "boards/common/adc_battery_monitor.h"

#include <esp_log.h>
#include <esp_lcd_panel_vendor.h>
#include <esp_lcd_panel_io.h>
#include <esp_lcd_panel_ops.h>
#include <driver/spi_common.h>
#include <driver/i2c_master.h>
#include <driver/uart.h>
#include "mcp_server.h"
#include "assets/lang_config.h"

#define TAG "XiaozhiCustomBoard"

class XiaozhiCustomBoard : public WifiBoard {
private:
    i2c_master_bus_handle_t i2c_bus_;
    Button boot_button_;
    Button volume_up_button_;
    Button volume_down_button_;
    LcdDisplay* display_;
    AdcBatteryMonitor* battery_monitor_;

    // 初始化 I2C 总线（用于 MPU-6500）
    void InitializeI2c() {
        i2c_master_bus_config_t i2c_cfg = {
            .i2c_port = I2C_NUM_0,
            .sda_io_num = IMU_I2C_SDA_PIN,
            .scl_io_num = IMU_I2C_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = { .enable_internal_pullup = 1 },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&i2c_cfg, &i2c_bus_));
    }

    // 初始化 SPI 总线（用于 ST7789 显示屏）
    void InitializeSpi() {
        spi_bus_config_t buscfg = {};
        buscfg.mosi_io_num = DISPLAY_MOSI_PIN;
        buscfg.miso_io_num = GPIO_NUM_NC;
        buscfg.sclk_io_num = DISPLAY_CLK_PIN;
        buscfg.quadwp_io_num = GPIO_NUM_NC;
        buscfg.quadhd_io_num = GPIO_NUM_NC;
        buscfg.max_transfer_sz = DISPLAY_WIDTH * DISPLAY_HEIGHT * sizeof(uint16_t);
        ESP_ERROR_CHECK(spi_bus_initialize(SPI3_HOST, &buscfg, SPI_DMA_CH_AUTO));
    }

    // 初始化 ST7789 LCD 显示屏
    void InitializeLcdDisplay() {
        esp_lcd_panel_io_handle_t panel_io = nullptr;
        esp_lcd_panel_handle_t panel = nullptr;

        ESP_LOGD(TAG, "Install panel IO");
        esp_lcd_panel_io_spi_config_t io_config = {};
        io_config.cs_gpio_num = DISPLAY_CS_PIN;
        io_config.dc_gpio_num = DISPLAY_DC_PIN;
        io_config.spi_mode = DISPLAY_SPI_MODE;
        io_config.pclk_hz = 40 * 1000 * 1000;
        io_config.trans_queue_depth = 10;
        io_config.lcd_cmd_bits = 8;
        io_config.lcd_param_bits = 8;
        ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi(SPI3_HOST, &io_config, &panel_io));

        ESP_LOGD(TAG, "Install LCD driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = DISPLAY_RST_PIN;
        panel_config.rgb_ele_order = DISPLAY_RGB_ORDER;
        panel_config.bits_per_pixel = 16;
        ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(panel_io, &panel_config, &panel));

        esp_lcd_panel_reset(panel);
        esp_lcd_panel_init(panel);
        esp_lcd_panel_invert_color(panel, DISPLAY_INVERT_COLOR);
        esp_lcd_panel_swap_xy(panel, DISPLAY_SWAP_XY);
        esp_lcd_panel_mirror(panel, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);

        display_ = new SpiLcdDisplay(panel_io, panel,
            DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_OFFSET_X, DISPLAY_OFFSET_Y,
            DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y, DISPLAY_SWAP_XY);
    }

    // 初始化按键
    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });

        volume_up_button_.OnClick([this]() {
            auto codec = GetAudioCodec();
            auto volume = codec->output_volume() + 10;
            if (volume > 100) volume = 100;
            codec->SetOutputVolume(volume);
            GetDisplay()->ShowNotification(Lang::Strings::VOLUME + std::to_string(volume));
        });

        volume_down_button_.OnClick([this]() {
            auto codec = GetAudioCodec();
            auto volume = codec->output_volume() - 10;
            if (volume < 0) volume = 0;
            codec->SetOutputVolume(volume);
            GetDisplay()->ShowNotification(Lang::Strings::VOLUME + std::to_string(volume));
        });
    }

    // 初始化电池电量检测
    void InitializeBatteryMonitor() {
        battery_monitor_ = new AdcBatteryMonitor(
            ADC_UNIT_1,                    // ADC1
            BATTERY_ADC_CHANNEL,           // ADC1_CH1 (IO2)
            BATTERY_UPPER_RESISTOR,        // 100k 上臂
            BATTERY_LOWER_RESISTOR,        // 100k 下臂
            GPIO_NUM_NC                    // 无充电检测引脚
        );
    }

    // ========== 机械臂 UART1 通信 ==========

    // 初始化 UART1（连接机械臂驱动板）
    void InitializeRobotUart() {
        uart_config_t uart_cfg = {
            .baud_rate = ROBOT_ARM_UART_BAUD_RATE,
            .data_bits = UART_DATA_8_BITS,
            .parity    = UART_PARITY_DISABLE,
            .stop_bits = UART_STOP_BITS_1,
            .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
            .source_clk = UART_SCLK_DEFAULT,
        };
        ESP_ERROR_CHECK(uart_driver_install(ROBOT_ARM_UART_PORT, ROBOT_ARM_UART_BUF_SIZE * 2, 0, 0, NULL, 0));
        ESP_ERROR_CHECK(uart_param_config(ROBOT_ARM_UART_PORT, &uart_cfg));
        ESP_ERROR_CHECK(uart_set_pin(ROBOT_ARM_UART_PORT, ROBOT_ARM_UART_TXD_PIN, ROBOT_ARM_UART_RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
        ESP_LOGI(TAG, "机械臂 UART1 初始化完成: TX=IO%d, RX=IO%d, %d bps", ROBOT_ARM_UART_TXD_PIN, ROBOT_ARM_UART_RXD_PIN, ROBOT_ARM_UART_BAUD_RATE);
    }

    // 发送 JSON 指令到机械臂驱动板（以换行符结尾）
    void SendRobotCommand(const std::string& json_cmd) {
        std::string msg = json_cmd + "\n";
        int written = uart_write_bytes(ROBOT_ARM_UART_PORT, msg.c_str(), msg.size());
        ESP_LOGI(TAG, "发送机械臂指令: %s (%d 字节)", json_cmd.c_str(), written);
    }

    // 注册机械臂 MCP 工具
    void InitializeRobotTools() {
        auto& mcp = McpServer::GetInstance();

        mcp.AddTool("robot.arm.move_joints",
            "控制机械臂6个关节的角度。angles为6个元素的JSON数组（度），speed为速度百分比（1-100）。",
            PropertyList({
                Property("angles", kPropertyTypeString),
                Property("speed", kPropertyTypeInteger, 50, 1, 100)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                auto angles_str = props["angles"].value<std::string>();
                int speed = props["speed"].value<int>();
                std::string cmd = "{\"cmd\":\"move_joints\",\"angles\":" + angles_str + ",\"speed\":" + std::to_string(speed) + "}";
                SendRobotCommand(cmd);
                return std::string("{\"status\":\"ok\"}");
            });

        mcp.AddTool("robot.arm.gripper",
            "控制夹爪开合。open=true为张开，open=false为闭合。speed为速度百分比（1-100）。",
            PropertyList({
                Property("open", kPropertyTypeBoolean),
                Property("speed", kPropertyTypeInteger, 50, 1, 100)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                bool open = props["open"].value<bool>();
                int speed = props["speed"].value<int>();
                std::string cmd = "{\"cmd\":\"gripper\",\"open\":" + std::string(open ? "true" : "false") + ",\"speed\":" + std::to_string(speed) + "}";
                SendRobotCommand(cmd);
                return std::string("{\"status\":\"ok\"}");
            });

        mcp.AddTool("robot.arm.get_status",
            "获取机械臂当前状态（关节角度、夹爪状态等）。",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                SendRobotCommand("{\"cmd\":\"get_status\"}");
                return std::string("{\"status\":\"pending\"}");
            });

        ESP_LOGI(TAG, "机械臂 MCP 工具注册完成（3个工具）");
    }

public:
    XiaozhiCustomBoard()
        : boot_button_(BOOT_BUTTON_GPIO)
        , volume_up_button_(VOLUME_UP_BUTTON_GPIO)
        , volume_down_button_(VOLUME_DOWN_BUTTON_GPIO) {
        ESP_LOGI(TAG, "Initializing XiaozhiCustomBoard");
        InitializeI2c();
        InitializeSpi();
        InitializeLcdDisplay();
        InitializeButtons();
        InitializeBatteryMonitor();
        InitializeRobotUart();     // 初始化机械臂 UART1
        InitializeRobotTools();    // 注册机械臂 MCP 工具
        if (DISPLAY_BACKLIGHT_PIN != GPIO_NUM_NC) {
            GetBacklight()->RestoreBrightness();
        }
        ESP_LOGI(TAG, "XiaozhiCustomBoard initialized successfully");
    }

    virtual AudioCodec* GetAudioCodec() override {
#ifdef AUDIO_I2S_METHOD_SIMPLEX
        static NoAudioCodecSimplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK,
            AUDIO_I2S_SPK_GPIO_LRCK,
            AUDIO_I2S_SPK_GPIO_DOUT,
            AUDIO_I2S_MIC_GPIO_SCK,
            AUDIO_I2S_MIC_GPIO_WS,
            AUDIO_I2S_MIC_GPIO_DIN);
#else
        static NoAudioCodecDuplex audio_codec(
            AUDIO_INPUT_SAMPLE_RATE,
            AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_GPIO_BCLK,
            AUDIO_I2S_GPIO_WS,
            AUDIO_I2S_GPIO_DOUT,
            AUDIO_I2S_GPIO_DIN);
#endif
        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }

    virtual Backlight* GetBacklight() override {
        if (DISPLAY_BACKLIGHT_PIN != GPIO_NUM_NC) {
            static PwmBacklight backlight(DISPLAY_BACKLIGHT_PIN, DISPLAY_BACKLIGHT_OUTPUT_INVERT);
            return &backlight;
        }
        return nullptr;
    }

    virtual Led* GetLed() override {
        static SingleLed led(BUILTIN_LED_GPIO);
        return &led;
    }

    virtual bool GetBatteryLevel(int& level, bool& charging, bool& discharging) override {
        if (battery_monitor_) {
            level = battery_monitor_->GetBatteryLevel();
            charging = battery_monitor_->IsCharging();
            discharging = battery_monitor_->IsDischarging();
            return true;
        }
        return false;
    }
};

DECLARE_BOARD(XiaozhiCustomBoard);