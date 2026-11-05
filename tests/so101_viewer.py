#!/usr/bin/env python3
r"""SO101 real robot arm MuJoCo interactive viewer
   模型来源: Argo-Robot/controls (GitHub)
   含 13 个 STL 网格 + 真实物理参数 + 6 关节舵机限位

   用法:
       C:\\Users\\XU\\.conda\\envs\\lerobot06\\python.exe tests\\so101_viewer.py

   交互:
       鼠标左键拖拽 = 旋转  |  右键拖拽 = 平移  |  滚轮 = 缩放
       Tab = 切换自由/跟踪相机  |  空格 = 暂停/恢复
       Ctrl + 右键 = 切换相机模式
"""

import mujoco
from mujoco import viewer
import numpy as np
import os
import time

# 切换到模型目录（XML 里的 meshdir="assets" 是相对路径）
MODEL_DIR = os.path.join(os.path.dirname(__file__), "so100_models")
os.chdir(MODEL_DIR)


def main():
    model = mujoco.MjModel.from_xml_path("scene.xml")
    data = mujoco.MjData(model)

    print("=" * 60)
    print("  SO101 真实机械臂 MuJoCo 仿真")
    print(f"  6 关节 + {model.nmesh} 个 STL 真实网格模型")
    print()
    print("  鼠标: 左键旋转 | 右键平移 | 滚轮缩放")
    print("  键盘: 空格暂停 | Tab 切相机 | Esc 退出")
    print()
    print("  关节范围（弧度/度）:")
    for i in range(model.nu):
        lo, hi = model.actuator_ctrlrange[i]
        print(f"    {model.actuator(i).name:16s}  [{lo:+.3f}, {hi:+.3f}] rad  =  [{lo*57.3:+.0f}, {hi*57.3:+.0f}] deg")
    print("=" * 60)

    mujoco.mj_forward(model, data)

    launcher = viewer.launch_passive(
        model, data,
        show_left_ui=True,
        show_right_ui=True,
    )

    launcher.sync()
    t0 = time.time()
    phase_offsets = [0, 1.2, 2.4, 3.6, 4.8, 6.0]

    with launcher as v:
        while v.is_running():
            t = time.time() - t0

            # 各关节正弦运动（在限位范围内小幅摆动）
            for i in range(6):
                lo, hi = model.actuator_ctrlrange[i]
                mid = (lo + hi) / 2
                amp = (hi - lo) * 0.25  # 1/4 范围摆动
                data.ctrl[i] = mid + amp * np.sin(t * 0.5 + phase_offsets[i])

            mujoco.mj_step(model, data)
            v.sync()


if __name__ == "__main__":
    main()
