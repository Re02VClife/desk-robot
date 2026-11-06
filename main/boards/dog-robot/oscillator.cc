#include "oscillator.h"

#include <cmath>

#include <driver/ledc.h>
#include <esp_err.h>
#include <esp_log.h>
#include <esp_timer.h>

#define TAG "Oscillator"

namespace {

// 一条腿一个 Oscillator，四个舵机共用同一个 LEDC 定时器（同为 50Hz），
// 各自必须占用**不同**的通道。原实现把每个舵机都配到 LEDC_CHANNEL_0，
// 四个腿会互相覆盖，只有最后初始化的那个能动。
constexpr ledc_mode_t kServoMode = LEDC_LOW_SPEED_MODE;
constexpr ledc_timer_t kServoTimer = LEDC_TIMER_0;
constexpr int kServoFreqHz = 50;
constexpr uint32_t kDutyMax = (1u << 16);

bool g_timer_configured = false;
int g_next_channel = 0;

}  // namespace

Oscillator::Oscillator() = default;

Oscillator::~Oscillator() {
    Detach();
}

void Oscillator::Attach(int pin) {
    if (pin < 0) {
        return;
    }

    if (!g_timer_configured) {
        ledc_timer_config_t timer_config = {};
        timer_config.speed_mode = kServoMode;
        timer_config.duty_resolution = LEDC_TIMER_16_BIT;
        timer_config.timer_num = kServoTimer;
        timer_config.freq_hz = kServoFreqHz;  // 舵机标准频率
        timer_config.clk_cfg = LEDC_AUTO_CLK;
        esp_err_t err = ledc_timer_config(&timer_config);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "ledc_timer_config failed: %s", esp_err_to_name(err));
            return;
        }
        g_timer_configured = true;
    }

    if (channel_ < 0) {
        if (g_next_channel >= LEDC_CHANNEL_MAX) {
            ESP_LOGE(TAG, "没有可用的 LEDC 通道了（最多 %d 个舵机）", LEDC_CHANNEL_MAX);
            return;
        }
        channel_ = g_next_channel++;
    }

    ledc_channel_config_t channel_config = {};
    channel_config.gpio_num = pin;
    channel_config.speed_mode = kServoMode;
    channel_config.channel = static_cast<ledc_channel_t>(channel_);
    channel_config.timer_sel = kServoTimer;
    channel_config.intr_type = LEDC_INTR_DISABLE;
    channel_config.duty = 0;
    channel_config.hpoint = 0;

    esp_err_t err = ledc_channel_config(&channel_config);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "ledc_channel_config(GPIO%d) failed: %s", pin, esp_err_to_name(err));
        channel_ = -1;
        return;
    }

    pin_ = pin;
}

void Oscillator::Detach() {
    if (pin_ != -1 && channel_ >= 0) {
        ledc_stop(kServoMode, static_cast<ledc_channel_t>(channel_), 0);
    }
    pin_ = -1;
}

void Oscillator::SetPosition(int position) {
    if (pin_ == -1 || channel_ < 0) {
        return;
    }

    int pos = position + trim_;
    if (pos < 0) {
        pos = 0;
    } else if (pos > 180) {
        pos = 180;
    }

    // SG90: 0.5ms~2.5ms 脉冲，50Hz(20ms 周期) 下对应 2.5%~12.5% 占空比
    const float duty_percent = 2.5f + (static_cast<float>(pos) / 180.0f) * 10.0f;
    const uint32_t duty_value = static_cast<uint32_t>((duty_percent / 100.0f) * kDutyMax);

    ledc_set_duty(kServoMode, static_cast<ledc_channel_t>(channel_), duty_value);
    ledc_update_duty(kServoMode, static_cast<ledc_channel_t>(channel_));

    pos_ = pos;
}

void Oscillator::Refresh() {
    if (paused_ || pin_ == -1) {
        return;
    }
    // T_ 为 0 时下面的 % 和 / 都是除零，直接返回
    if (T_ <= 0) {
        return;
    }

    const long current_millis = millis();
    if (current_millis - previous_servo_command_millis_ < 10) {
        return;
    }

    const double phase = (2.0 * M_PI * static_cast<double>(current_millis % T_)) / static_cast<double>(T_) +
                         (static_cast<double>(Ph_) * M_PI / 180.0);
    int pos = O_ + static_cast<int>(static_cast<double>(A_) * std::sin(phase));

    if (limiter_enabled_ && diff_limit_ > 0) {
        const int diff = std::abs(pos - pos_);
        if (diff > diff_limit_) {
            pos = (pos > pos_) ? pos_ + diff_limit_ : pos_ - diff_limit_;
        }
    }

    SetPosition(pos);
    previous_servo_command_millis_ = current_millis;
}

void Oscillator::SetLimiter(int diff_limit) {
    limiter_enabled_ = true;
    diff_limit_ = diff_limit;
}

long Oscillator::millis() {
    return static_cast<long>(esp_timer_get_time() / 1000);
}
