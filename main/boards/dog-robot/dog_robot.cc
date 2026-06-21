#include "dog_robot.h"
#include "board.h"
#include "mcp_server.h"
#include <esp_log.h>

#define TAG "DogRobot"

DogRobot::DogRobot() {
    // 初始化舵机引脚
    servo_pins_[FRONT_LEFT] = -1;
    servo_pins_[FRONT_RIGHT] = -1;
    servo_pins_[BACK_LEFT] = -1;
    servo_pins_[BACK_RIGHT] = -1;
    
    // 初始化舵机偏移量
    for (int i = 0; i < SERVO_COUNT; i++) {
        servo_trim_[i] = 0;
    }
}

DogRobot::~DogRobot() {
    // 释放舵机资源
    for (int i = 0; i < SERVO_COUNT; i++) {
        if (servo_pins_[i] != -1) {
            servo_[i].Detach();
        }
    }
}

void DogRobot::Initialize(int front_left, int front_right, int back_left, int back_right) {
    // 设置舵机引脚
    servo_pins_[FRONT_LEFT] = front_left;
    servo_pins_[FRONT_RIGHT] = front_right;
    servo_pins_[BACK_LEFT] = back_left;
    servo_pins_[BACK_RIGHT] = back_right;
    
    // 初始化舵机
    for (int i = 0; i < SERVO_COUNT; i++) {
        if (servo_pins_[i] != -1) {
            servo_[i].Attach(servo_pins_[i]);
            servo_[i].SetTrim(servo_trim_[i]);
        }
    }
    
    ESP_LOGI(TAG, "Dog robot initialized with servos: FL=%d, FR=%d, BL=%d, BR=%d", 
             front_left, front_right, back_left, back_right);
}

void DogRobot::SetTrim(int front_left, int front_right, int back_left, int back_right) {
    servo_trim_[FRONT_LEFT] = front_left;
    servo_trim_[FRONT_RIGHT] = front_right;
    servo_trim_[BACK_LEFT] = back_left;
    servo_trim_[BACK_RIGHT] = back_right;
    
    // 应用偏移量
    for (int i = 0; i < SERVO_COUNT; i++) {
        if (servo_pins_[i] != -1) {
            servo_[i].SetTrim(servo_trim_[i]);
        }
    }
}

void DogRobot::MoveServos(int time, int servo_target[]) {
    float increment[SERVO_COUNT];
    
    // 计算每个舵机的增量
    for (int i = 0; i < SERVO_COUNT; i++) {
        if (servo_pins_[i] != -1) {
            increment[i] = (servo_target[i] - servo_[i].GetPosition()) / (time / 10.0);
        }
    }
    
    // 逐步移动舵机
    for (int t = 0; t < time; t += 10) {
        for (int i = 0; i < SERVO_COUNT; i++) {
            if (servo_pins_[i] != -1) {
                servo_[i].SetPosition(servo_[i].GetPosition() + increment[i]);
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
    
    // 确保舵机到达目标位置
    for (int i = 0; i < SERVO_COUNT; i++) {
        if (servo_pins_[i] != -1) {
            servo_[i].SetPosition(servo_target[i]);
        }
    }
}

void DogRobot::MoveSingle(int position, int servo_number) {
    if (servo_number >= 0 && servo_number < SERVO_COUNT && servo_pins_[servo_number] != -1) {
        servo_[servo_number].SetPosition(position);
    }
}

void DogRobot::Stand() {
    int target[SERVO_COUNT] = {90, 90, 90, 90};
    MoveServos(500, target);
}

void DogRobot::Walk(int steps, int speed) {
    for (int i = 0; i < steps; i++) {
        // 第一步：左前腿和右后腿向前
        int step1[SERVO_COUNT] = {120, 60, 60, 120};
        MoveServos(speed, step1);
        
        // 第二步：左前腿和右后腿向后，右前腿和左后腿向前
        int step2[SERVO_COUNT] = {60, 120, 120, 60};
        MoveServos(speed, step2);
    }
    
    // 回到站立姿势
    Stand();
}

void DogRobot::TurnLeft(int steps, int speed) {
    for (int i = 0; i < steps; i++) {
        // 左转第一步
        int step1[SERVO_COUNT] = {130, 70, 50, 130};
        MoveServos(speed, step1);
        
        // 左转第二步
        int step2[SERVO_COUNT] = {50, 130, 130, 70};
        MoveServos(speed, step2);
    }
    
    // 回到站立姿势
    Stand();
}

void DogRobot::TurnRight(int steps, int speed) {
    for (int i = 0; i < steps; i++) {
        // 右转第一步
        int step1[SERVO_COUNT] = {70, 130, 130, 50};
        MoveServos(speed, step1);
        
        // 右转第二步
        int step2[SERVO_COUNT] = {130, 70, 70, 130};
        MoveServos(speed, step2);
    }
    
    // 回到站立姿势
    Stand();
}

void DogRobot::Wave() {
    // 简单的挥手动作
    int wave1[SERVO_COUNT] = {110, 90, 90, 90};
    MoveServos(300, wave1);
    
    int wave2[SERVO_COUNT] = {70, 90, 90, 90};
    MoveServos(300, wave2);
    
    int wave3[SERVO_COUNT] = {110, 90, 90, 90};
    MoveServos(300, wave3);
    
    int wave4[SERVO_COUNT] = {70, 90, 90, 90};
    MoveServos(300, wave4);
    
    // 回到站立姿势
    Stand();
}

void DogRobot::InitializeTools() {
    auto& mcp_server = McpServer::GetInstance();
    
    // 添加机器狗控制工具
    mcp_server.AddTool("self.dog_robot.stand",
        "让机器狗站立",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            Stand();
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.walk",
        "让机器狗行走",
        PropertyList({
            Property("steps", kPropertyTypeInteger, 5, 1, 20),
            Property("speed", kPropertyTypeInteger, 200, 50, 500)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int steps = properties["steps"].value<int>();
            int speed = properties["speed"].value<int>();
            Walk(steps, speed);
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.turn_left",
        "让机器狗向左转",
        PropertyList({
            Property("steps", kPropertyTypeInteger, 3, 1, 10),
            Property("speed", kPropertyTypeInteger, 200, 50, 500)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int steps = properties["steps"].value<int>();
            int speed = properties["speed"].value<int>();
            TurnLeft(steps, speed);
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.turn_right",
        "让机器狗向右转",
        PropertyList({
            Property("steps", kPropertyTypeInteger, 3, 1, 10),
            Property("speed", kPropertyTypeInteger, 200, 50, 500)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int steps = properties["steps"].value<int>();
            int speed = properties["speed"].value<int>();
            TurnRight(steps, speed);
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.wave",
        "让机器狗挥手",
        PropertyList(),
        [this](const PropertyList& properties) -> ReturnValue {
            Wave();
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.move_servo",
        "单独控制一个舵机",
        PropertyList({
            Property("servo", kPropertyTypeInteger, 0, 0, 3),
            Property("position", kPropertyTypeInteger, 90, 0, 180)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int servo = properties["servo"].value<int>();
            int position = properties["position"].value<int>();
            MoveSingle(position, servo);
            return true;
        });
    
    mcp_server.AddTool("self.dog_robot.set_trim",
        "设置舵机偏移量",
        PropertyList({
            Property("front_left", kPropertyTypeInteger, 0, -20, 20),
            Property("front_right", kPropertyTypeInteger, 0, -20, 20),
            Property("back_left", kPropertyTypeInteger, 0, -20, 20),
            Property("back_right", kPropertyTypeInteger, 0, -20, 20)
        }),
        [this](const PropertyList& properties) -> ReturnValue {
            int fl = properties["front_left"].value<int>();
            int fr = properties["front_right"].value<int>();
            int bl = properties["back_left"].value<int>();
            int br = properties["back_right"].value<int>();
            SetTrim(fl, fr, bl, br);
            return true;
        });
}
