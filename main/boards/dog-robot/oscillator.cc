#include "oscillator.h"
#include <math.h>
#include <esp_timer.h>
#include <driver/ledc.h>

//-- Generate sinusoidal oscillations in the servos

void Oscillator::Attach(int pin) {
    pin_ = pin;
    
    // 配置LED PWM控制器
    ledc_timer_config_t timer_config = {
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .duty_resolution = LEDC_TIMER_16_BIT,
        .timer_num = LEDC_TIMER_0,
        .freq_hz = 50,  // 舵机标准频率
        .clk_cfg = LEDC_AUTO_CLK
    };
    ledc_timer_config(&timer_config);
    
    // 配置LED PWM通道
    ledc_channel_config_t channel_config = {
        .gpio_num = (gpio_num_t)pin,
        .speed_mode = LEDC_LOW_SPEED_MODE,
        .channel = LEDC_CHANNEL_0,
        .timer_sel = LEDC_TIMER_0,
        .duty = 0,
        .hpoint = 0
    };
    ledc_channel_config(&channel_config);
}

void Oscillator::Detach() {
    if (pin_ != -1) {
        ledc_stop(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, 0);
        pin_ = -1;
    }
}

void Oscillator::SetPosition(int position) {
    if (pin_ == -1) return;
    
    int pos = position + trim_;
    // 限制角度范围
    if (pos < 0) pos = 0;
    if (pos > 180) pos = 180;
    
    // 将角度转换为PWM占空比
    // SG90舵机：0.5ms - 2.5ms脉冲，对应0-180度
    // 50Hz频率，周期20ms
    // 占空比范围：2.5% - 12.5%
    float duty = 2.5 + (pos / 180.0) * 10.0;
    uint32_t duty_value = (uint32_t)((duty / 100.0) * (1 << 16));
    
    ledc_set_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0, duty_value);
    ledc_update_duty(LEDC_LOW_SPEED_MODE, LEDC_CHANNEL_0);
    
    pos_ = pos;
}
