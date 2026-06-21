#ifndef DOG_ROBOT_H
#define DOG_ROBOT_H

#include "oscillator.h"
#include "mcp_server.h"

class DogRobot {
public:
    // 舵机编号
    enum ServoIndex {
        FRONT_LEFT = 0,
        FRONT_RIGHT = 1,
        BACK_LEFT = 2,
        BACK_RIGHT = 3,
        SERVO_COUNT = 4
    };
    
    DogRobot();
    ~DogRobot();
    
    // 初始化方法
    void Initialize(int front_left, int front_right, int back_left, int back_right);
    
    // 设置舵机偏移量
    void SetTrim(int front_left, int front_right, int back_left, int back_right);
    
    // 控制方法
    void MoveServos(int time, int servo_target[]);
    void MoveSingle(int position, int servo_number);
    
    // 预设动作
    void Stand();
    void Walk(int steps, int speed);
    void TurnLeft(int steps, int speed);
    void TurnRight(int steps, int speed);
    void Wave();
    
    // MCP工具初始化
    void InitializeTools();
    
private:
    Oscillator servo_[SERVO_COUNT];
    int servo_pins_[SERVO_COUNT];
    int servo_trim_[SERVO_COUNT];
};

#endif // DOG_ROBOT_H
