#include "board.h"
#include "dog_robot.h"
#include "wifi_board.h"
#include "audio_codec.h"
#include "display.h"
#include "oled_display.h"
#include "led.h"
#include "backlight.h"
#include <esp_log.h>

#define TAG "DogRobotBoard"

class DogRobotBoard : public WifiBoard {
public:
    DogRobotBoard() : WifiBoard() {
        dog_robot_ = std::make_unique<DogRobot>();
    }
    
    ~DogRobotBoard() override {
    }
    
    void Initialize() override {
        WifiBoard::Initialize();
        
        // 初始化机器狗舵机
        // 这里使用默认引脚，实际使用时需要根据硬件连接修改
        int front_left = 12;   // 前左腿舵机
        int front_right = 13;  // 前右腿舵机
        int back_left = 14;    // 后左腿舵机
        int back_right = 15;   // 后右腿舵机
        
        dog_robot_->Initialize(front_left, front_right, back_left, back_right);
        
        // 初始化MCP工具
        dog_robot_->InitializeTools();
        
        ESP_LOGI(TAG, "Dog robot board initialized");
    }
    
    std::string GetBoardName() const override {
        return "dog-robot";
    }
    
    std::string GetDeviceType() const override {
        return "dog_robot";
    }
    
private:
    std::unique_ptr<DogRobot> dog_robot_;
};

// 注册板型
BOARD_REGISTER(DogRobotBoard, dog_robot);
