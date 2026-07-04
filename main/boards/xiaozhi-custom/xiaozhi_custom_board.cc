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
#include <esp_rom_sys.h>
#include <driver/spi_common.h>
#include <driver/i2c_master.h>
#include <cJSON.h>
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

    // ========== 机械臂 UART1 通信（SCServo 二进制协议） ==========

    // SCServo 控制表地址（型号 252，字节地址，小端序）
    static constexpr uint8_t SCS_ADDR_TORQUE  = 40;  // 扭矩使能
    static constexpr uint8_t SCS_ADDR_GOAL    = 42;  // 目标位置（2字节）
    static constexpr uint8_t SCS_ADDR_SPEED   = 46;  // 目标速度（2字节）
    static constexpr uint8_t SCS_ADDR_PRESENT = 56;  // 当前位置（2字节，只读）

    // 各关节限位 [CW最小, CCW最大]（步值，4096步=360°）
    // 角度 0°→CW 限位，180°→CCW 限位
    static constexpr uint16_t JOINT_LIMITS[6][2] = {
        {1100, 2900},  // 关节1 底座
        { 800, 3100},  // 关节2 大臂
        { 800, 2990},  // 关节3 小臂
        { 950, 3000},  // 关节4 腕转
        { 800, 3900},  // 关节5 腕俯
        {2000, 3400},  // 关节6 夹爪
    };

    // SCServo 校验和：~(id + len + inst + ... + params) & 0xFF
    static uint8_t ScsChecksum(const uint8_t* data, size_t len) {
        uint8_t sum = 0;
        for (size_t i = 0; i < len; i++) sum += data[i];
        return ~sum;
    }

    // 写入 1 字节到舵机控制表
    static void ScsWriteByte(uint8_t sid, uint8_t addr, uint8_t value) {
        uint8_t pkt[8];
        pkt[0] = 0xFF; pkt[1] = 0xFF;
        pkt[2] = sid;
        pkt[3] = 4;       // length = params(2) + inst(1) + cksum(1)
        pkt[4] = 0x03;    // INST_WRITE
        pkt[5] = addr;
        pkt[6] = value;
        pkt[7] = ScsChecksum(&pkt[2], 5);
        uart_write_bytes(ROBOT_ARM_UART_PORT, pkt, 8);
        esp_rom_delay_us(200);
    }

    // 写入 16 位值到舵机控制表（小端序）
    static void ScsWriteWord(uint8_t sid, uint8_t addr, uint16_t value) {
        uint8_t pkt[9];
        pkt[0] = 0xFF; pkt[1] = 0xFF;
        pkt[2] = sid;
        pkt[3] = 5;       // length = params(3) + inst(1) + cksum(1)
        pkt[4] = 0x03;    // INST_WRITE
        pkt[5] = addr;
        pkt[6] = (uint8_t)(value & 0xFF);
        pkt[7] = (uint8_t)((value >> 8) & 0xFF);
        pkt[8] = ScsChecksum(&pkt[2], 6);
        uart_write_bytes(ROBOT_ARM_UART_PORT, pkt, 9);
        esp_rom_delay_us(200);
    }

    // 读取 16 位值
    static uint16_t ScsReadWord(uint8_t sid, uint8_t addr) {
        uint8_t pkt[8];
        pkt[0] = 0xFF; pkt[1] = 0xFF;
        pkt[2] = sid;
        pkt[3] = 4;
        pkt[4] = 0x02;    // INST_READ
        pkt[5] = addr;
        pkt[6] = 2;       // 读 2 字节
        pkt[7] = ScsChecksum(&pkt[2], 5);
        uart_flush_input(ROBOT_ARM_UART_PORT);
        uart_write_bytes(ROBOT_ARM_UART_PORT, pkt, 8);
        esp_rom_delay_us(500);
        uint8_t reply[8];
        int len = uart_read_bytes(ROBOT_ARM_UART_PORT, reply, 8, pdMS_TO_TICKS(30));
        if (len >= 8 && reply[0] == 0xFF && reply[1] == 0xFF && reply[4] == 0) {
            return reply[5] | ((uint16_t)reply[6] << 8);
        }
        return 0xFFFF;  // 读取失败标识
    }

    // 角度（0-180°）→ 步值映射，按各关节限位线性插值
    static uint16_t AngleToSteps(int joint, double angle) {
        if (joint < 0 || joint > 5) return 0;
        // 安全裁剪
        if (angle < 0.0) angle = 0.0;
        if (angle > 180.0) angle = 180.0;
        uint16_t cw  = JOINT_LIMITS[joint][0];
        uint16_t ccw = JOINT_LIMITS[joint][1];
        return (uint16_t)(cw + (angle / 180.0) * (ccw - cw));
    }

    // 初始化 UART1（直连 SO101 舵机总线）
    void InitializeRobotUart() {
        uart_config_t uart_cfg = {
            .baud_rate = ROBOT_ARM_UART_BAUD_RATE,
            .data_bits = UART_DATA_8_BITS,
            .parity    = UART_PARITY_DISABLE,
            .stop_bits = UART_STOP_BITS_1,
            .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
            .source_clk = UART_SCLK_DEFAULT,
        };
        ESP_ERROR_CHECK(uart_driver_install(ROBOT_ARM_UART_PORT, ROBOT_ARM_UART_BUF_SIZE * 2, ROBOT_ARM_UART_BUF_SIZE * 2, 0, NULL, 0));
        ESP_ERROR_CHECK(uart_param_config(ROBOT_ARM_UART_PORT, &uart_cfg));
        ESP_ERROR_CHECK(uart_set_pin(ROBOT_ARM_UART_PORT, ROBOT_ARM_UART_TXD_PIN, ROBOT_ARM_UART_RXD_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
        ESP_LOGI(TAG, "机械臂 UART1 初始化完成: TX=IO%d, RX=IO%d, %d bps (SCServo直连)", ROBOT_ARM_UART_TXD_PIN, ROBOT_ARM_UART_RXD_PIN, ROBOT_ARM_UART_BAUD_RATE);

        // 上电使能全部 6 个舵机扭矩
        for (uint8_t sid = 1; sid <= 6; sid++) {
            ScsWriteByte(sid, SCS_ADDR_TORQUE, 1);
            esp_rom_delay_us(100);
        }
        ESP_LOGI(TAG, "6 个舵机扭矩已使能");
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

                // 速度映射: 1-100 → SCServo 5-500（0.1RPM 单位）
                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                cJSON* angles_json = cJSON_Parse(angles_str.c_str());
                if (!angles_json || !cJSON_IsArray(angles_json)) {
                    if (angles_json) cJSON_Delete(angles_json);
                    return std::string("{\"status\":\"error\",\"message\":\"angles 格式错误\"}");
                }

                int count = cJSON_GetArraySize(angles_json);
                if (count > 6) count = 6;

                // 先设速度，再设目标位置
                for (int i = 0; i < count; i++) {
                    cJSON* item = cJSON_GetArrayItem(angles_json, i);
                    if (cJSON_IsNumber(item)) {
                        double angle = item->valuedouble;
                        if (angle < 0.0) angle = 0.0;
                        if (angle > 180.0) angle = 180.0;
                        uint16_t steps = AngleToSteps(i, angle);
                        uint8_t sid = (uint8_t)(i + 1);
                        ScsWriteWord(sid, SCS_ADDR_SPEED, scs_speed);
                        ScsWriteWord(sid, SCS_ADDR_GOAL, steps);
                    }
                }
                cJSON_Delete(angles_json);
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

                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                // 夹爪(ID6): CW=2000(最开), CCW=3400(最合)
                // 张开→2100, 闭合→2400（留 30 步限位余量）
                uint16_t steps = open ? 2100 : 2400;

                ScsWriteWord(6, SCS_ADDR_SPEED, scs_speed);
                ScsWriteWord(6, SCS_ADDR_GOAL, steps);
                return std::string(open ? "{\"status\":\"ok\",\"gripper\":\"open\"}" : "{\"status\":\"ok\",\"gripper\":\"close\"}");
            });

        mcp.AddTool("robot.arm.get_status",
            "获取机械臂当前状态（6个关节的当前位置和角度）。",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                // 读取 6 个关节当前位置
                int16_t positions[6];
                for (uint8_t sid = 1; sid <= 6; sid++) {
                    uint16_t raw = ScsReadWord(sid, SCS_ADDR_PRESENT);
                    positions[sid - 1] = (raw == 0xFFFF) ? -1 : (int16_t)raw;
                }

                // 构建 JSON 响应
                cJSON* root = cJSON_CreateObject();
                cJSON_AddStringToObject(root, "status", "ok");
                cJSON* pos_array = cJSON_CreateArray();
                cJSON* deg_array = cJSON_CreateArray();
                for (int i = 0; i < 6; i++) {
                    cJSON_AddItemToArray(pos_array, cJSON_CreateNumber(positions[i]));
                    double deg = (positions[i] >= 0) ? (positions[i] / 4096.0 * 360.0) : -1.0;
                    cJSON_AddItemToArray(deg_array, cJSON_CreateNumber(deg));
                }
                cJSON_AddItemToObject(root, "positions", pos_array);
                cJSON_AddItemToObject(root, "degrees", deg_array);
                char* result = cJSON_PrintUnformatted(root);
                std::string ret(result);
                cJSON_free(result);
                cJSON_Delete(root);
                return ret;
            });

        ESP_LOGI(TAG, "机械臂 MCP 工具注册完成（3个工具，SCServo直连）");
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