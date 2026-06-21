#ifndef OSCILLATOR_H
#define OSCILLATOR_H

//-- Generate sinusoidal oscillations in the servos
class Oscillator {
public:
    Oscillator() : pos_(0), pin_(-1), trim_(0), O_(0), A_(0), T_(0), Ph_(0), 
                  previous_servo_command_millis_(0), limiter_enabled_(false), 
                  diff_limit_(0), paused_(false) {}
    
    void Attach(int pin) {
        pin_ = pin;
        // 初始化舵机引脚
        // 这里使用ESP32的PWM功能控制舵机
        // 实际实现需要根据ESP-IDF的API来实现
    }
    
    void Detach() {
        pin_ = -1;
    }
    
    void SetPosition(int position) {
        if (pin_ == -1) return;
        
        int pos = position + trim_;
        // 限制角度范围
        if (pos < 0) pos = 0;
        if (pos > 180) pos = 180;
        
        pos_ = pos;
        // 发送PWM信号到舵机
        // 实际实现需要根据ESP-IDF的API来实现
    }
    
    int GetPosition() const {
        return pos_;
    }
    
    void SetTrim(int trim) {
        trim_ = trim;
    }
    
    void SetO(int offset) {
        O_ = offset;
    }
    
    void SetA(int amplitude) {
        A_ = amplitude;
    }
    
    void SetT(int period) {
        T_ = period;
    }
    
    void SetPh(int phase) {
        Ph_ = phase;
    }
    
    void Refresh() {
        if (paused_ || pin_ == -1) return;
        
        long currentMillis = millis();
        if (currentMillis - previous_servo_command_millis_ >= 10) {
            int pos = O_ + A_ * sin(2 * M_PI * (currentMillis % T_) / T_ + Ph_ * M_PI / 180);
            
            if (limiter_enabled_) {
                int diff = abs(pos - pos_);
                if (diff > diff_limit_) {
                    if (pos > pos_) {
                        pos = pos_ + diff_limit_;
                    } else {
                        pos = pos_ - diff_limit_;
                    }
                }
            }
            
            SetPosition(pos);
            previous_servo_command_millis_ = currentMillis;
        }
    }
    
    void SetLimiter(int diff_limit) {
        limiter_enabled_ = true;
        diff_limit_ = diff_limit;
    }
    
    void DisableLimiter() {
        limiter_enabled_ = false;
    }
    
    void Pause() {
        paused_ = true;
    }
    
    void Resume() {
        paused_ = false;
    }
    
private:
    int pos_;                       //-- Current servo pos
    int pin_;                       //-- Pin where the servo is connected
    int trim_;                      //-- Trim for servo calibration
    int O_;                         //-- Offset
    int A_;                         //-- Amplitude
    int T_;                         //-- Period (ms)
    int Ph_;                        //-- Phase (degrees 0-360)
    bool limiter_enabled_;          //-- If true, the position change is limited
    int diff_limit_;                //-- Max position change per refresh
    bool paused_;                   //-- Oscillation mode. If true, the servo is stopped
    long previous_servo_command_millis_;
    
    // 模拟millis()函数
    long millis() {
        return (long)(esp_timer_get_time() / 1000);
    }
};

#endif // OSCILLATOR_H
