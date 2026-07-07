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
#include <cstdio>
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
    Button touch_button_;       // IO3 触摸传感器
    int touch_count_ = 0;       // 摸头计数器（用于多样化响应）
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

        // 触摸传感器：被摸头时触发多样化交互
        touch_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            auto state = app.GetDeviceState();
            // 只在空闲或听音状态响应触摸
            if (state != kDeviceStateIdle && state != kDeviceStateListening) {
                ESP_LOGI(TAG, "摸头触发被忽略（当前状态: %d）", (int)state);
                return;
            }

            // 多样化提示词池（14种，每次轮换）
            static const char* TOUCH_PROMPTS[] = {
                "有人摸了摸我的头！好开心～",
                "欸？谁在摸我的头呀？",
                "嘿嘿，被摸头了，感觉好幸福～",
                "啊！偷袭摸头！那我要撒个娇～",
                "又被摸头了啦～头发都要乱掉了！",
                "唔…摸头杀！我要蹦跶一下表示开心",
                "嘻嘻，摸头的感觉真好～摇摇手臂庆祝一下",
                "咦？被发现了吗？摸摸头好舒服哦",
                "哇！被摸头了！让我扭一扭～",
                "嗯哼～不要一直摸啦，会害羞的！",
                "啊哈！摸头攻击！我要做个可爱的动作回应",
                "有人宠我耶～好开心！转个圈圈",
                "嘿嘿嘿，被摸头的感觉会上瘾欸～",
                "呜哇～又被偷袭了！这次我要做个不一样的反应",
            };
            int idx = touch_count_ % 14;
            touch_count_++;
            std::string msg = TOUCH_PROMPTS[idx];
            ESP_LOGI(TAG, "触摸触发 (第%d次): %s", touch_count_, msg.c_str());
            GetDisplay()->ShowNotification("摸摸头 ❤️");
            app.SendTextInput(msg);
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

    // 确保6个舵机扭矩全部使能（急停后恢复用）
    static void EnsureTorqueEnabled() {
        for (uint8_t sid = 1; sid <= 6; sid++) {
            uint16_t state = ScsReadWord(sid, SCS_ADDR_TORQUE);
            if (state != 1) {
                ScsWriteByte(sid, SCS_ADDR_TORQUE, 1);
                ESP_LOGW(TAG, "关节%d 扭矩已恢复", sid);
            }
        }
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

        // HOME 位置（步值，2026-06-30 实测）
        static constexpr uint16_t HOME_STEPS[6] = {2019, 805, 2979, 2869, 1082, 2246};
        // 关节限位转换为角度参考（0°=CW极限, 180°=CCW极限）
        static constexpr const char* JOINT_REF =
            "关节索引: 1=底座旋转, 2=大臂俯仰, 3=小臂俯仰, 4=手腕旋转, 5=手腕俯仰, 6=夹爪开合\n"
            "安全范围(度): 1[97~255] 2[70~273] 3[70~263] 4[84~264] 5[70~343] 6[176~299]\n"
            "HOME姿态(度): [92, 0, 179, 169, 16, 32]";

        // ========== robot.arm.move_joints（增强：支持增量模式） ==========
        mcp.AddTool("robot.arm.move_joints",
            "控制机械臂6个关节的绝对角度。未指定的关节保持当前位置不动。\n" + std::string(JOINT_REF) + "\n"
            "参数: angles=6个元素的JSON数组字符串（度，0-180）\n"
            "参数: speed=速度1-100（默认50）\n"
            "参数: relative=增量模式（默认false）。为true时angles表示相对当前位置的偏移量",
            PropertyList({
                Property("angles", kPropertyTypeString),
                Property("speed", kPropertyTypeInteger, 50, 1, 100),
                Property("relative", kPropertyTypeBoolean, false)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                auto angles_str = props["angles"].value<std::string>();
                int speed = props["speed"].value<int>();
                bool relative = props["relative"].value<bool>();

                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                EnsureTorqueEnabled();  // 急停后恢复扭矩

                cJSON* angles_json = cJSON_Parse(angles_str.c_str());
                if (!angles_json || !cJSON_IsArray(angles_json)) {
                    if (angles_json) cJSON_Delete(angles_json);
                    return std::string("{\"status\":\"error\",\"message\":\"angles 格式错误，需要JSON数组\"}");
                }

                int count = cJSON_GetArraySize(angles_json);
                if (count > 6) count = 6;

                // 第一遍：收集目标角度
                double targets[6] = {0};
                bool valid[6] = {false};
                for (int i = 0; i < count; i++) {
                    cJSON* item = cJSON_GetArrayItem(angles_json, i);
                    if (!cJSON_IsNumber(item)) continue;
                    targets[i] = item->valuedouble;
                    valid[i] = true;

                    if (relative) {
                        uint16_t current = ScsReadWord((uint8_t)(i + 1), SCS_ADDR_PRESENT);
                        if (current == 0xFFFF) { valid[i] = false; continue; }
                        uint16_t cw  = JOINT_LIMITS[i][0];
                        uint16_t ccw = JOINT_LIMITS[i][1];
                        targets[i] = (double)(current - cw) / (ccw - cw) * 180.0 + targets[i];
                    }
                }
                cJSON_Delete(angles_json);

                // 安全校验：关节2过低 → 限制关节1旋转幅度
                if (valid[1] && targets[1] < 15.0 && valid[0]) {
                    uint16_t j1_raw = ScsReadWord(1, SCS_ADDR_PRESENT);
                    if (j1_raw != 0xFFFF) {
                        double j1_cur = (double)(j1_raw - JOINT_LIMITS[0][0]) / (JOINT_LIMITS[0][1] - JOINT_LIMITS[0][0]) * 180.0;
                        if (targets[0] > j1_cur + 15.0) {
                            ESP_LOGW(TAG, "安全锁: 关节2=%.0f°过低, 关节1 %.0f→%.0f°(限制+15°)", targets[1], targets[0], j1_cur+15.0);
                            targets[0] = j1_cur + 15.0;
                        } else if (targets[0] < j1_cur - 15.0) {
                            ESP_LOGW(TAG, "安全锁: 关节2=%.0f°过低, 关节1 %.0f→%.0f°(限制-15°)", targets[1], targets[0], j1_cur-15.0);
                            targets[0] = j1_cur - 15.0;
                        }
                    }
                }
                // 安全校验：关节3过低 → 禁止关节2大幅下降
                if (valid[2] && targets[2] < 20.0 && valid[1]) {
                    uint16_t j2_raw = ScsReadWord(2, SCS_ADDR_PRESENT);
                    if (j2_raw != 0xFFFF) {
                        double j2_cur = (double)(j2_raw - JOINT_LIMITS[1][0]) / (JOINT_LIMITS[1][1] - JOINT_LIMITS[1][0]) * 180.0;
                        if (targets[1] < j2_cur - 10.0) {
                            ESP_LOGW(TAG, "安全锁: 关节3=%.0f°过低, 关节2禁止下降 (%.0f→%.0f°)", targets[2], targets[1], j2_cur);
                            targets[1] = j2_cur;
                        }
                    }
                }

                // 第二遍：裁剪并下发
                cJSON* result = cJSON_CreateObject();
                cJSON_AddStringToObject(result, "status", "ok");
                cJSON* applied = cJSON_CreateArray();
                for (int i = 0; i < 6; i++) {
                    if (!valid[i]) {
                        cJSON_AddItemToArray(applied, cJSON_CreateNull());
                        continue;
                    }
                    if (targets[i] < 0.0) targets[i] = 0.0;
                    if (targets[i] > 180.0) targets[i] = 180.0;

                    uint8_t sid = (uint8_t)(i + 1);
                    uint16_t steps = AngleToSteps(i, targets[i]);
                    ScsWriteWord(sid, SCS_ADDR_SPEED, scs_speed);
                    ScsWriteWord(sid, SCS_ADDR_GOAL, steps);
                    cJSON_AddItemToArray(applied, cJSON_CreateNumber(targets[i]));
                }
                cJSON_AddItemToObject(result, "angles_applied", applied);
                cJSON_AddBoolToObject(result, "relative", relative);
                char* json_str = cJSON_PrintUnformatted(result);
                std::string ret(json_str);
                cJSON_free(json_str);
                cJSON_Delete(result);
                return ret;
            });

        // ========== robot.arm.move_joint（单关节控制） ==========
        mcp.AddTool("robot.arm.move_joint",
            "控制机械臂单个关节的角度。适合微调单一关节，比move_joints更简单。\n" + std::string(JOINT_REF) + "\n"
            "参数: joint=关节编号1-6\n"
            "参数: angle=目标角度0-180（度）\n"
            "参数: speed=速度1-100（默认30）",
            PropertyList({
                Property("joint", kPropertyTypeInteger, 1, 6),
                Property("angle", kPropertyTypeInteger, 0, 180),
                Property("speed", kPropertyTypeInteger, 30, 1, 100)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                int joint = props["joint"].value<int>();
                int angle = props["angle"].value<int>();
                int speed = props["speed"].value<int>();

                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                EnsureTorqueEnabled();  // 急停后恢复扭矩

                uint8_t sid = (uint8_t)joint;
                uint16_t steps = AngleToSteps(joint - 1, (double)angle);

                ScsWriteWord(sid, SCS_ADDR_SPEED, scs_speed);
                ScsWriteWord(sid, SCS_ADDR_GOAL, steps);

                // 读取实际到位位置确认
                esp_rom_delay_us(3000);
                uint16_t actual = ScsReadWord(sid, SCS_ADDR_PRESENT);
                char buf[256];
                snprintf(buf, sizeof(buf),
                    "{\"status\":\"ok\",\"joint\":%d,\"target_angle\":%d,\"target_steps\":%u,\"actual_steps\":%u}",
                    joint, angle, steps, actual);
                return std::string(buf);
            });

        // ========== robot.arm.home（归位） ==========
        mcp.AddTool("robot.arm.home",
            "一键归位：机械臂6个关节全部回到已知的HOME安全姿态。"
            "适用场景：机械臂姿态混乱时恢复到已知状态。速度默认60。",
            PropertyList({
                Property("speed", kPropertyTypeInteger, 60, 1, 100)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                int speed = props["speed"].value<int>();
                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                EnsureTorqueEnabled();  // 急停后恢复扭矩

                for (uint8_t sid = 1; sid <= 6; sid++) {
                    ScsWriteWord(sid, SCS_ADDR_SPEED, scs_speed);
                    ScsWriteWord(sid, SCS_ADDR_GOAL, HOME_STEPS[sid - 1]);
                }
                return std::string("{\"status\":\"ok\",\"action\":\"home\"}");
            });

        // ========== robot.arm.stop（急停） ==========
        mcp.AddTool("robot.arm.stop",
            "紧急停止：立即释放全部6个舵机的扭矩，机械臂会因重力自然下垂。"
            "⚠️ 释放扭矩后需调用robot.arm.home恢复控制。"
            "适用场景：机械臂即将碰撞或出现异常动作时紧急停止。",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                for (uint8_t sid = 1; sid <= 6; sid++) {
                    ScsWriteByte(sid, SCS_ADDR_TORQUE, 0);
                }
                ESP_LOGW(TAG, "⚠️ 急停！6个舵机扭矩已释放");
                return std::string("{\"status\":\"ok\",\"action\":\"emergency_stop\",\"warning\":\"舵机扭矩已释放，请调用robot.arm.home恢复\"}");
            });

        // ========== robot.arm.gripper（增强：支持精确位置） ==========
        mcp.AddTool("robot.arm.gripper",
            "控制夹爪开合。可通过open参数控制开/合，或通过position参数精确控制开度。\n"
            "关节6夹爪: 张开≈2100步(0°), 闭合≈2400步(180°)\n"
            "参数: open=true张开/false闭合（与position二选一）\n"
            "参数: position=精确目标角度0-180（可选，覆盖open参数）\n"
            "参数: speed=速度1-100（默认30）",
            PropertyList({
                Property("open", kPropertyTypeBoolean, true),
                Property("speed", kPropertyTypeInteger, 30, 1, 100),
                Property("position", kPropertyTypeInteger, -1)
            }),
            [this](const PropertyList& props) -> ReturnValue {
                bool open = props["open"].value<bool>();
                int speed = props["speed"].value<int>();
                int position = props["position"].value<int>();

                uint16_t scs_speed = (uint16_t)(speed * 5);
                if (scs_speed < 5) scs_speed = 5;

                uint16_t steps;
                const char* desc;
                if (position >= 0) {
                    // 精确位置模式：position参数优先
                    double angle = (double)position;
                    if (angle < 0.0) angle = 0.0;
                    if (angle > 180.0) angle = 180.0;
                    steps = AngleToSteps(5, angle);  // 关节6 索引5
                    desc = "position";
                } else {
                    // 二态模式：使用open参数
                    steps = open ? 2100 : 2400;
                    desc = open ? "open" : "close";
                }

                ScsWriteWord(6, SCS_ADDR_SPEED, scs_speed);
                ScsWriteWord(6, SCS_ADDR_GOAL, steps);

                char buf[128];
                snprintf(buf, sizeof(buf),
                    "{\"status\":\"ok\",\"gripper\":\"%s\",\"steps\":%u}", desc, steps);
                return std::string(buf);
            });

        // ========== robot.arm.get_status（增强：更多字段） ==========
        mcp.AddTool("robot.arm.get_status",
            "获取机械臂完整状态：6个关节的当前位置、物理角度、偏离HOME的偏移量、扭矩状态。\n"
            "每次移动前建议先调用此工具了解当前姿态，避免危险操作。",
            PropertyList(),
            [this](const PropertyList& props) -> ReturnValue {
                cJSON* root = cJSON_CreateObject();
                cJSON_AddStringToObject(root, "status", "ok");

                cJSON* joints = cJSON_CreateArray();
                for (uint8_t sid = 1; sid <= 6; sid++) {
                    cJSON* j = cJSON_CreateObject();
                    cJSON_AddNumberToObject(j, "id", sid);

                    // 位置（步值 + 物理角度）
                    uint16_t pos = ScsReadWord(sid, SCS_ADDR_PRESENT);
                    double phys_deg = (pos != 0xFFFF) ? (pos / 4096.0 * 360.0) : -1.0;
                    cJSON_AddNumberToObject(j, "steps", (pos != 0xFFFF) ? (int)pos : -1);
                    cJSON_AddNumberToObject(j, "physical_deg", phys_deg);

                    // 映射角度（0-180 归一化，与 move_joints 一致）
                    int idx = sid - 1;
                    uint16_t cw  = JOINT_LIMITS[idx][0];
                    uint16_t ccw = JOINT_LIMITS[idx][1];
                    double mapped_deg = (pos != 0xFFFF)
                        ? (double)(pos - cw) / (ccw - cw) * 180.0
                        : -1.0;
                    if (mapped_deg < 0.0) mapped_deg = 0.0;
                    if (mapped_deg > 180.0) mapped_deg = 180.0;
                    cJSON_AddNumberToObject(j, "angle", mapped_deg);

                    // 偏离 HOME 的偏移
                    int home_step = HOME_STEPS[idx];
                    int offset_steps = (pos != 0xFFFF) ? (int)pos - home_step : 0;
                    cJSON_AddNumberToObject(j, "home_offset_steps", offset_steps);

                    // 扭矩状态（读地址40）
                    uint16_t torque_raw = ScsReadWord(sid, SCS_ADDR_TORQUE);
                    bool torque_on = (torque_raw != 0xFFFF && torque_raw == 1);
                    cJSON_AddBoolToObject(j, "torque_enabled", torque_on);

                    cJSON_AddItemToArray(joints, j);
                }
                cJSON_AddItemToObject(root, "joints", joints);

                char* json_str = cJSON_PrintUnformatted(root);
                std::string ret(json_str);
                cJSON_free(json_str);
                cJSON_Delete(root);
                return ret;
            });

        // 急停后需重新使能扭矩，在 move_joints/move_joint/home 中自动恢复
        // （ScsWriteWord 写位置时，舵机如果扭矩关闭会忽略命令，所以需要此逻辑）
        // 此处不自动恢复——让用户显式调用 home 来恢复控制

        ESP_LOGI(TAG, "机械臂 MCP 工具注册完成（6个工具，SCServo直连）");
    }

public:
    XiaozhiCustomBoard()
        : boot_button_(BOOT_BUTTON_GPIO)
        , volume_up_button_(VOLUME_UP_BUTTON_GPIO)
        , volume_down_button_(VOLUME_DOWN_BUTTON_GPIO)
        , touch_button_(TOUCH_BUTTON_GPIO) {
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