#ifndef OSCILLATOR_H
#define OSCILLATOR_H

//-- Generate sinusoidal oscillations in the servos
//
// 只在这里声明，实现全部在 oscillator.cc。
// 以前 .h 里写了一份空壳内联实现、.cc 里又写一份真实现，
// 同一个类被定义两次，一旦这块板真的参与编译就是 redefinition 错误。
class Oscillator {
public:
    Oscillator();
    ~Oscillator();

    void Attach(int pin);
    void Detach();

    void SetPosition(int position);
    int GetPosition() const { return pos_; }

    void SetTrim(int trim) { trim_ = trim; }
    void SetO(int offset) { O_ = offset; }
    void SetA(int amplitude) { A_ = amplitude; }
    void SetT(int period) { T_ = period; }
    void SetPh(int phase) { Ph_ = phase; }

    void Refresh();

    void SetLimiter(int diff_limit);
    void DisableLimiter() { limiter_enabled_ = false; }

    void Pause() { paused_ = true; }
    void Resume() { paused_ = false; }

private:
    long millis();

    int pos_ = 0;                              //-- Current servo pos
    int pin_ = -1;                             //-- Pin where the servo is connected
    int trim_ = 0;                             //-- Trim for servo calibration
    int O_ = 0;                                //-- Offset
    int A_ = 0;                                //-- Amplitude
    int T_ = 0;                                //-- Period (ms)
    int Ph_ = 0;                               //-- Phase (degrees 0-360)
    bool limiter_enabled_ = false;             //-- If true, the position change is limited
    int diff_limit_ = 0;                       //-- Max position change per refresh
    bool paused_ = false;                      //-- Oscillation mode. If true, the servo is stopped
    long previous_servo_command_millis_ = 0;
    int channel_ = -1;                         //-- 该舵机独占的 LEDC 通道
};

#endif // OSCILLATOR_H
