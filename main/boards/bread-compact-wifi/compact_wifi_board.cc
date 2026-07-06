#include "wifi_board.h"
#include "codecs/no_audio_codec.h"
#include "display/oled_display.h"
#include "system_reset.h"
#include "application.h"
#include "button.h"
#include "config.h"
#include "mcp_server.h"
#include "led/single_led.h"
#include "assets/lang_config.h"

#include <esp_log.h>
#include <driver/i2c_master.h>
#include <driver/ledc.h>
#include <esp_lcd_panel_ops.h>
#include <esp_lcd_panel_vendor.h>

#ifdef SH1106
#include <esp_lcd_panel_sh1106.h>
#endif

#define TAG "CompactWifiBoard"

// ========== 机器狗舵机驱动（LEDC PWM, 50Hz） ==========
static constexpr uint32_t SERVO_PWM_FREQ = 50;        // 50Hz
static constexpr ledc_timer_t SERVO_TIMER = LEDC_TIMER_0;
static constexpr ledc_mode_t SERVO_MODE = LEDC_LOW_SPEED_MODE;
static constexpr ledc_timer_bit_t SERVO_DUTY_RES = LEDC_TIMER_14_BIT;  // 0~16383
static constexpr uint32_t SERVO_DUTY_MAX = (1 << 14) - 1;  // 16383
// 舵机脉宽范围: 500us(0°) ~ 2500us(180°), 周期20ms
static constexpr uint32_t SERVO_MIN_US = 500;
static constexpr uint32_t SERVO_MAX_US = 2500;

static const struct {
    const char* name;
    gpio_num_t pin;
} servo_pins[] = {
    {"右前", SERVO_RIGHT_FRONT_PIN},   // GPIO 13
    {"右后", SERVO_RIGHT_BACK_PIN},    // GPIO 14
    {"左前", SERVO_LEFT_FRONT_PIN},    // GPIO 17
    {"左后", SERVO_LEFT_BACK_PIN},     // GPIO 18
};

// ========== 触摸传感器 ==========
static const struct {
    const char* name;
    gpio_num_t pin;
} touch_pins[] = {
    {"左触", TOUCH_SENSOR_LEFT_PIN},    // GPIO 8
    {"前触", TOUCH_SENSOR_FRONT_PIN},   // GPIO 19
    {"右触", TOUCH_SENSOR_RIGHT_PIN},   // GPIO 20
};

// 角度→脉宽→duty 转换
static uint32_t AngleToDuty(int angle) {
    if (angle < 0) angle = 0;
    if (angle > 180) angle = 180;
    uint32_t pulse_us = SERVO_MIN_US + (uint32_t)(angle / 180.0f * (SERVO_MAX_US - SERVO_MIN_US));
    return (pulse_us * (SERVO_DUTY_MAX + 1)) / 20000;
}

static void ServoSetAngle(int servo_index, int angle) {
    if (servo_index < 0 || servo_index > 3) return;
    uint32_t duty = AngleToDuty(angle);
    ESP_ERROR_CHECK(ledc_set_duty(SERVO_MODE, (ledc_channel_t)servo_index, duty));
    ESP_ERROR_CHECK(ledc_update_duty(SERVO_MODE, (ledc_channel_t)servo_index));
}

class CompactWifiBoard : public WifiBoard {
private:
    i2c_master_bus_handle_t display_i2c_bus_;
    esp_lcd_panel_io_handle_t panel_io_ = nullptr;
    esp_lcd_panel_handle_t panel_ = nullptr;
    Display* display_ = nullptr;
    Button boot_button_;
    Button touch_button_;
    Button volume_up_button_;
    Button volume_down_button_;

    void InitializeDisplayI2c() {
        i2c_master_bus_config_t bus_config = {
            .i2c_port = (i2c_port_t)0,
            .sda_io_num = DISPLAY_SDA_PIN,
            .scl_io_num = DISPLAY_SCL_PIN,
            .clk_source = I2C_CLK_SRC_DEFAULT,
            .glitch_ignore_cnt = 7,
            .intr_priority = 0,
            .trans_queue_depth = 0,
            .flags = {
                .enable_internal_pullup = 1,
            },
        };
        ESP_ERROR_CHECK(i2c_new_master_bus(&bus_config, &display_i2c_bus_));
    }

    void InitializeSsd1306Display() {
        // SSD1306 config
        esp_lcd_panel_io_i2c_config_t io_config = {
            .dev_addr = 0x3C,
            .on_color_trans_done = nullptr,
            .user_ctx = nullptr,
            .control_phase_bytes = 1,
            .dc_bit_offset = 6,
            .lcd_cmd_bits = 8,
            .lcd_param_bits = 8,
            .flags = {
                .dc_low_on_data = 0,
                .disable_control_phase = 0,
            },
            .scl_speed_hz = 400 * 1000,
        };

        ESP_ERROR_CHECK(esp_lcd_new_panel_io_i2c_v2(display_i2c_bus_, &io_config, &panel_io_));

        ESP_LOGI(TAG, "Install SSD1306 driver");
        esp_lcd_panel_dev_config_t panel_config = {};
        panel_config.reset_gpio_num = -1;
        panel_config.bits_per_pixel = 1;

        esp_lcd_panel_ssd1306_config_t ssd1306_config = {
            .height = static_cast<uint8_t>(DISPLAY_HEIGHT),
        };
        panel_config.vendor_config = &ssd1306_config;

#ifdef SH1106
        ESP_ERROR_CHECK(esp_lcd_new_panel_sh1106(panel_io_, &panel_config, &panel_));
#else
        ESP_ERROR_CHECK(esp_lcd_new_panel_ssd1306(panel_io_, &panel_config, &panel_));
#endif
        ESP_LOGI(TAG, "SSD1306 driver installed");

        // Reset the display
        ESP_ERROR_CHECK(esp_lcd_panel_reset(panel_));
        if (esp_lcd_panel_init(panel_) != ESP_OK) {
            ESP_LOGE(TAG, "Failed to initialize display");
            display_ = new NoDisplay();
            return;
        }
        ESP_ERROR_CHECK(esp_lcd_panel_invert_color(panel_, false));

        // Set the display to on
        ESP_LOGI(TAG, "Turning display on");
        ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(panel_, true));

        display_ = new OledDisplay(panel_io_, panel_, DISPLAY_WIDTH, DISPLAY_HEIGHT, DISPLAY_MIRROR_X, DISPLAY_MIRROR_Y);
    }

    void InitializeButtons() {
        boot_button_.OnClick([this]() {
            auto& app = Application::GetInstance();
            if (app.GetDeviceState() == kDeviceStateStarting) {
                EnterWifiConfigMode();
                return;
            }
            app.ToggleChatState();
        });
        touch_button_.OnPressDown([this]() {
            Application::GetInstance().StartListening();
        });
        touch_button_.OnPressUp([this]() {
            Application::GetInstance().StopListening();
        });

        volume_up_button_.OnClick([this]() {
            auto codec = GetAudioCodec();
            auto volume = codec->output_volume() + 10;
            if (volume > 100) {
                volume = 100;
            }
            codec->SetOutputVolume(volume);
            GetDisplay()->ShowNotification(Lang::Strings::VOLUME + std::to_string(volume));
        });

        volume_up_button_.OnLongPress([this]() {
            GetAudioCodec()->SetOutputVolume(100);
            GetDisplay()->ShowNotification(Lang::Strings::MAX_VOLUME);
        });

        volume_down_button_.OnClick([this]() {
            auto codec = GetAudioCodec();
            auto volume = codec->output_volume() - 10;
            if (volume < 0) {
                volume = 0;
            }
            codec->SetOutputVolume(volume);
            GetDisplay()->ShowNotification(Lang::Strings::VOLUME + std::to_string(volume));
        });

        volume_down_button_.OnLongPress([this]() {
            GetAudioCodec()->SetOutputVolume(0);
            GetDisplay()->ShowNotification(Lang::Strings::MUTED);
        });
    }

    // 初始化舵机 PWM（LEDC 4 通道）
    void InitializeServos() {
        ledc_timer_config_t timer_cfg = {
            .speed_mode = SERVO_MODE,
            .duty_resolution = SERVO_DUTY_RES,
            .timer_num = SERVO_TIMER,
            .freq_hz = SERVO_PWM_FREQ,
            .clk_cfg = LEDC_AUTO_CLK,
        };
        ESP_ERROR_CHECK(ledc_timer_config(&timer_cfg));

        for (int i = 0; i < 4; i++) {
            ledc_channel_config_t ch_cfg = {
                .gpio_num = (int)servo_pins[i].pin,
                .speed_mode = SERVO_MODE,
                .channel = (ledc_channel_t)i,
                .intr_type = LEDC_INTR_DISABLE,
                .timer_sel = SERVO_TIMER,
                .duty = AngleToDuty(90),  // 初始 90°（中位）
                .hpoint = 0,
                .flags = { .output_invert = 0 },
            };
            ESP_ERROR_CHECK(ledc_channel_config(&ch_cfg));
            ESP_LOGI(TAG, "舵机 %s 初始化: GPIO%d, 中位=90°", servo_pins[i].name, servo_pins[i].pin);
        }
    }

    // 初始化触摸传感器（GPIO 输入 + 内部上拉）
    void InitializeTouchSensors() {
        for (int i = 0; i < 3; i++) {
            gpio_config_t cfg = {
                .pin_bit_mask = (1ULL << touch_pins[i].pin),
                .mode = GPIO_MODE_INPUT,
                .pull_up_en = GPIO_PULLUP_ENABLE,
                .pull_down_en = GPIO_PULLDOWN_DISABLE,
                .intr_type = GPIO_INTR_DISABLE,
            };
            ESP_ERROR_CHECK(gpio_config(&cfg));
            ESP_LOGI(TAG, "触摸 %s 初始化: GPIO%d", touch_pins[i].name, touch_pins[i].pin);
        }
    }

    // 注册机器狗 MCP 工具
    void InitializeDogTools() {
        auto& mcp = McpServer::GetInstance();

        // dog.servo.set_angle — 控制单个舵机角度
        mcp.AddTool("dog.servo.set_angle",
            "设置机器狗单个舵机角度（0-180°）。servo: right_front/right_back/left_front/left_back",
            PropertyList({
                Property("servo", kPropertyTypeString),
                Property("angle", kPropertyTypeInteger, 90, 0, 180),
            }),
            [](const PropertyList& props) -> ReturnValue {
                auto servo_name = props["servo"].value<std::string>();
                int angle = props["angle"].value<int>();
                int idx = -1;
                if (servo_name == "right_front") idx = 0;
                else if (servo_name == "right_back") idx = 1;
                else if (servo_name == "left_front") idx = 2;
                else if (servo_name == "left_back") idx = 3;
                else return std::string("{\"status\":\"error\",\"message\":\"无效的舵机名\"}");

                ServoSetAngle(idx, angle);
                ESP_LOGI(TAG, "舵机 %s → %d°", servo_pins[idx].name, angle);
                return std::string("{\"status\":\"ok\"}");
            });

        // dog.servo.set_all — 批量设置 4 个舵机
        mcp.AddTool("dog.servo.set_all",
            "设置 4 个舵机角度。angles: [右前,右后,左前,左后]，每个 0-180°",
            PropertyList({
                Property("angles", kPropertyTypeString),  // JSON 数组字符串
            }),
            [](const PropertyList& props) -> ReturnValue {
                auto angles_str = props["angles"].value<std::string>();
                cJSON* arr = cJSON_Parse(angles_str.c_str());
                if (!arr || !cJSON_IsArray(arr)) {
                    if (arr) cJSON_Delete(arr);
                    return std::string("{\"status\":\"error\",\"message\":\"格式错误\"}");
                }
                int count = cJSON_GetArraySize(arr);
                if (count > 4) count = 4;
                for (int i = 0; i < count; i++) {
                    cJSON* item = cJSON_GetArrayItem(arr, i);
                    if (cJSON_IsNumber(item)) {
                        ServoSetAngle(i, (int)item->valuedouble);
                        ESP_LOGI(TAG, "舵机 %s → %d°", servo_pins[i].name, (int)item->valuedouble);
                    }
                }
                cJSON_Delete(arr);
                return std::string("{\"status\":\"ok\"}");
            });

        // dog.servo.center — 全部回中位 90°
        mcp.AddTool("dog.servo.center",
            "所有 4 个舵机回到中位（90°）",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                for (int i = 0; i < 4; i++) {
                    ServoSetAngle(i, 90);
                }
                ESP_LOGI(TAG, "全部舵机 → 中位");
                return std::string("{\"status\":\"ok\"}");
            });

        // dog.touch.read — 读取 3 个触摸传感器状态
        mcp.AddTool("dog.touch.read",
            "读取 3 个触须传感器状态（按下=1, 未按=0）",
            PropertyList(),
            [](const PropertyList& props) -> ReturnValue {
                char buf[128];
                int left  = gpio_get_level(TOUCH_SENSOR_LEFT_PIN) == 0 ? 1 : 0;
                int front = gpio_get_level(TOUCH_SENSOR_FRONT_PIN) == 0 ? 1 : 0;
                int right = gpio_get_level(TOUCH_SENSOR_RIGHT_PIN) == 0 ? 1 : 0;
                snprintf(buf, sizeof(buf),
                    "{\"status\":\"ok\",\"left\":%d,\"front\":%d,\"right\":%d}", left, front, right);
                return std::string(buf);
            });

        ESP_LOGI(TAG, "机器狗 MCP 工具注册完成（4个舵机+1个触摸读取）");
    }

public:
    CompactWifiBoard() :
        boot_button_(BOOT_BUTTON_GPIO),
        touch_button_(TOUCH_BUTTON_GPIO),
        volume_up_button_(VOLUME_UP_BUTTON_GPIO),
        volume_down_button_(VOLUME_DOWN_BUTTON_GPIO) {
        InitializeDisplayI2c();
        InitializeSsd1306Display();
        InitializeButtons();
        InitializeServos();
        InitializeTouchSensors();
        InitializeDogTools();
        ESP_LOGI(TAG, "机器狗 CompactWifiBoard 初始化完成");
    }

    virtual Led* GetLed() override {
        static SingleLed led(BUILTIN_LED_GPIO);
        return &led;
    }

    virtual AudioCodec* GetAudioCodec() override {
#ifdef AUDIO_I2S_METHOD_SIMPLEX
        static NoAudioCodecSimplex audio_codec(AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_SPK_GPIO_BCLK, AUDIO_I2S_SPK_GPIO_LRCK, AUDIO_I2S_SPK_GPIO_DOUT, AUDIO_I2S_MIC_GPIO_SCK, AUDIO_I2S_MIC_GPIO_WS, AUDIO_I2S_MIC_GPIO_DIN);
#else
        static NoAudioCodecDuplex audio_codec(AUDIO_INPUT_SAMPLE_RATE, AUDIO_OUTPUT_SAMPLE_RATE,
            AUDIO_I2S_GPIO_BCLK, AUDIO_I2S_GPIO_WS, AUDIO_I2S_GPIO_DOUT, AUDIO_I2S_GPIO_DIN);
#endif
        return &audio_codec;
    }

    virtual Display* GetDisplay() override {
        return display_;
    }
};

DECLARE_BOARD(CompactWifiBoard);
