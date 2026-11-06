#include "wifi_board.h"
#include "dog_robot.h"

#include <esp_log.h>
#include <memory>

#define TAG "DogRobotBoard"

// 四个 SG90 舵机（见 boards/dog-robot/README.md 的接线表）
static constexpr int kServoFrontLeft = 12;
static constexpr int kServoFrontRight = 13;
static constexpr int kServoBackLeft = 14;
static constexpr int kServoBackRight = 15;

class DogRobotBoard : public WifiBoard {
public:
    // 板级初始化统一放在构造函数里：Board 没有虚的 Initialize()，
    // 上层只会调 Board::GetInstance()，构造函数是唯一一定会执行的地方。
    DogRobotBoard() : dog_robot_(std::make_unique<DogRobot>()) {
        ESP_LOGI(TAG, "Initializing DogRobotBoard");
        dog_robot_->Initialize(kServoFrontLeft, kServoFrontRight, kServoBackLeft, kServoBackRight);
        dog_robot_->InitializeTools();
        ESP_LOGI(TAG, "DogRobotBoard initialized");
    }

    virtual std::string GetBoardType() override { return "dog-robot"; }

private:
    std::unique_ptr<DogRobot> dog_robot_;
};

DECLARE_BOARD(DogRobotBoard);
