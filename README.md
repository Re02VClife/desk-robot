# desk-robot · ESP32-S3 桌面 AI 机器人

> 一块自己画的 ESP32-S3 主板 + 一只会用语音对话的四足机器狗。

基于开源项目 [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)（小智 AI 语音助手）二次开发：
保留上游 80 种官方开发板支持，新增了**自定义 PCB 主板**和**SG90 四足机器狗**两套板级实现。

| 项 | 说明 |
|---|---|
| 主控 | ESP32-S3-WROOM-1-N16R8（16 MB Flash / 8 MB Octal PSRAM） |
| 框架 | ESP-IDF v5.5.2+ |
| 显示 | ST7789 2.0" 240×320 SPI |
| 交互 | 语音唤醒 + 大模型对话 + MCP 工具调用 |
| 扩展 | 4×SG90 舵机四足机器狗、MPU-6500 六轴 IMU |

---

## 目录

- [它能做什么](#它能做什么)
- [硬件](#硬件)
- [快速开始](#快速开始)
- [目录结构](#目录结构)
- [文档](#文档)
- [已知限制](#已知限制)
- [致谢与许可](#致谢与许可)

---

## 它能做什么

**语音助手（主板 `xiaozhi-custom`）**

- 说「你好小智」唤醒，接入大模型进行多轮语音对话
- 240×320 彩屏显示表情与状态，WS2812B 灯效随状态变化
- BOOT 键短按切换对话状态，长按进入 WiFi 配网
- VOL+/VOL- 调节音量，ADC 实时检测电池电量
- 首次串口烧录，之后通过 WiFi OTA 双分区升级（失败自动回滚）

**机器狗（扩展板 `dog-robot`）**

- 语音指令直接控制：站起来、走 5 步、向左转 3 步、挥手……
- 通过 MCP 工具暴露 7 个动作接口（`stand` / `walk` / `turn_left` / `turn_right` / `wave` / `move_servo` / `set_trim`），大模型可自由编排
- 每个舵机支持 ±20° 偏移校准，解决 SG90 装配误差导致的走偏

---

## 硬件

### 主板 `xiaozhi-custom`

完整引脚映射、BOM 与选型说明见 **[基本介绍.md](基本介绍.md)**。

| 功能 | 引脚 |
|---|---|
| 麦克风 ZTS6672（I2S） | LRC=IO4, DIN=IO5, BCLK=IO6 |
| 功放 CH98357 / MAX98357A | DIN=IO7（BCLK/LRC 与麦克风共用） |
| 屏幕 ST7789（SPI，U7 连接器） | SCL=IO21, SDA=IO47, RES=IO45, DC=IO40, CS=IO41, BLK=IO42 |
| IMU MPU-6500（I2C 0x68） | SDA=IO11, SCL=IO12 |
| RGB LED WS2812B | IO48 |
| 按键 | BOOT=IO0, VOL+=IO38, VOL-=IO39 |
| 电池检测 | IO2（ADC1_CH1，100k/100k 分压） |
| 扩展口 | CN1=IO17/18/19/20，CN2=IO8/37/42/1 |

> ⚠️ **必须使用 U7 显示连接器**。板上另一个 8pin 排针的 IO11/IO12 与 MPU-6500 的 I2C 总线冲突，不要同时焊接。

### 机器狗扩展板 `dog-robot`

| 舵机 | 引脚 | 说明 |
|---|---|---|
| 前左腿 | GPIO12 | 0=前左 |
| 前右腿 | GPIO13 | 1=前右 |
| 后左腿 | GPIO14 | 2=后左 |
| 后右腿 | GPIO15 | 3=后右 |

供电建议 5V/2A 以上，SG90 堵转电流会瞬时拉低电压。接线、校准与故障排查见 **[main/boards/dog-robot/README.md](main/boards/dog-robot/README.md)**。

> 注：机器狗使用独立扩展板，舵机占用的 IO12–IO15 与主板 IMU 的 I2C 引脚**不要在同一块板上同时连接**。

---

## 快速开始

### 1. 准备环境

- [ESP-IDF](https://docs.espressif.com/projects/esp-idf/zh_CN/latest/esp32s3/get-started/) **v5.5.2 及以上**（推荐 v5.5.3）
- 串口驱动 CH340（板载调试口通过 JP1 引出 IO43/IO44）

### 2. 编译

```bash
# 在 ESP-IDF 终端中，于仓库根目录执行
idf.py set-target esp32s3
idf.py menuconfig
```

在 `menuconfig` 中确认：

- `Xiaozhi Assistant → Board Type` → **XiaoZhi Custom PCB**（机器狗选 **Dog Robot**）
- `Serial flasher config → Flash size` → **16 MB**

```bash
idf.py build
```

### 3. 烧录

```bash
idf.py -p COMx flash monitor      # Windows
idf.py -p /dev/ttyUSB0 flash monitor   # Linux / macOS
```

手动进入下载模式：按住 **BOOT(IO0)** → 按一下 **EN** → 松开 EN → 松开 BOOT。

### 4. 联网与升级

首次上电后长按 BOOT 进入配网模式，用手机连接设备热点完成配置。之后固件可通过 WiFi OTA 升级，双 OTA 分区保证升级失败能自动回滚。

---

## 目录结构

```
desk-robot/
├── main/
│   ├── boards/              # 板级实现（80 种上游板 + xiaozhi-custom + dog-robot）
│   │   ├── xiaozhi-custom/  # 自定义主板：config.h / config.json / 板级初始化
│   │   ├── dog-robot/       # 四足机器狗：舵机驱动 + 步态振荡器 + MCP 工具
│   │   └── common/          # 各板共用的音频、显示、电源代码
│   ├── audio/  display/  led/  protocols/   # 音频编解码、LVGL 显示、灯效、通信协议
│   ├── application.cc       # 应用主循环与状态机
│   ├── mcp_server.cc        # MCP 工具注册与调用
│   └── ota.cc               # OTA 升级与回滚
├── docs/                    # 开发文档（自定义板、MCP、MQTT/UDP、WebSocket）
├── scripts/                 # 构建与发布脚本（release.py 等）
├── partitions/              # 分区表（v2/16m.csv：双 OTA 4MB + 8MB 资源区）
├── sdkconfig.defaults       # 公共编译配置
└── sdkconfig.defaults.esp32s3
```

---

## 文档

| 文档 | 内容 |
|---|---|
| [基本介绍.md](基本介绍.md) | 主板硬件：引脚映射、BOM、编译烧录、注意事项 |
| [docs/custom-board.md](docs/custom-board.md) | 如何新增一块自定义板 |
| [docs/mcp-protocol.md](docs/mcp-protocol.md) / [docs/mcp-usage.md](docs/mcp-usage.md) | MCP 协议与用法 |
| [docs/mqtt-udp.md](docs/mqtt-udp.md) | MQTT + UDP 通信协议 |
| [docs/websocket.md](docs/websocket.md) | WebSocket 通信协议 |
| [docs/code_style.md](docs/code_style.md) | 代码风格约定 |
| [docs/团队协作指南.md](docs/团队协作指南.md) | 协作流程 |

---

## 已知限制

1. **功放 SD 引脚硬件常开**（R1 = 1 MΩ 上拉到 5V），软件无法关断功放，静态功耗偏高。
2. **ZTS6672 麦克风**在小智项目中没有现成驱动，I2S 时序与 INMP441 兼容但需实测确认拾音质量。
3. **MPU-6500 尚未接入姿态融合**，目前只预留了 I2C 引脚，运动控制板（轮足平衡）规划中。
4. **CN2 的 IO42 与屏幕背光共用**，占用该口时背光会受影响。
5. 编译必须使用 ESP-IDF ≥ 5.5.2；4.x 无法通过组件依赖解析。

---

## 致谢与许可

本项目基于 [78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)（v2.2.4）二次开发，感谢原项目及 ESP-IDF 生态的开源工作。

以 [MIT License](LICENSE) 发布，著作权遵循上游声明。
