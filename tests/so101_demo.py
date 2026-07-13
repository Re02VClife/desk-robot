#!/usr/bin/env python3
r"""SO101 simulation usage demo — control, render, VLA integration preview
   Usage:
       C:\Users\XU\.conda\envs\lerobot06\python.exe tests\so101_demo.py
"""

import mujoco
from mujoco import viewer
import numpy as np
import os
import time

os.chdir(os.path.join(os.path.dirname(__file__), "so100_models"))
model = mujoco.MjModel.from_xml_path("scene.xml")
data = mujoco.MjData(model)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. 设置关节角度 (控制机械臂)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def set_joints(*angles_deg):
    """设 6 个关节角度（度），直接设 qpos + forward"""
    for i, ang in enumerate(angles_deg):
        lo, hi = model.actuator_ctrlrange[i]
        # 同时设 qpos（运动学）和 ctrl（致动器目标）
        data.qpos[i] = np.clip(np.radians(ang), lo, hi)
        data.ctrl[i] = data.qpos[i]
    mujoco.mj_forward(model, data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. 获取末端位置 (用于抓取规划)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_end_effector_pos():
    """返回夹爪末端的世界坐标"""
    site_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "gripperframe")
    return data.site_xpos[site_id].copy()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. 渲染相机画面 (VLA 输入)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_camera(width=224, height=224):
    """从固定视角渲染图像——这就是 VLA 模型的输入"""
    r = mujoco.Renderer(model, height, width)
    mujoco.mj_forward(model, data)
    r.update_scene(data)
    img = r.render()
    r.close()
    return img  # shape: (224, 224, 3) uint8 RGB


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. 在仿真场景里加一个方块（抓取目标）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def add_cube(x=0.15, y=0.15, z=0.05, size=0.02, color=(1, 0.2, 0.2, 1)):
    """动态添加被抓物体（需重新加载模型，或手动改 XML）"""
    # 简便法：直接改 data——但 MuJoCo 不允许运行时加 geoms
    # 生产环境请写到 scene.xml 的 <worldbody> 里
    print(f"  (添加方块请编辑 scene.xml: <geom type='box' pos='{x} {y} {z}' size='{size} {size} {size}' rgba='{color[0]} {color[1]} {color[2]} {color[3]}'/>)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DEMO：演示上述功能
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if __name__ == "__main__":
    print("=" * 55)
    print("  SO101 仿真使用指南")
    print("=" * 55)

    # --- 演示 1: 控制关节 ---
    print("\n[1] 设置关节角度到 HOME 位置...")
    set_joints(0, -30, 60, 0, -30, 0)
    mujoco.mj_forward(model, data)
    ee = get_end_effector_pos()
    print(f"     末端位置: x={ee[0]:.4f}  y={ee[1]:.4f}  z={ee[2]:.4f}")

    # --- 演示 2: 渲染 ---
    print("\n[2] 渲染一帧图像（VLA 模型输入格式）...")
    img = render_camera(224, 224)
    print(f"     图像: {img.shape}, dtype={img.dtype}, 值域 [{img.min()}, {img.max()}]")
    print(f"     这张图可以直接送给 smolVLA / pi0 / ACT 做推理")

    # --- 演示 3: 关节扫描 ---
    print("\n[3] 扫描关节 1（底座旋转）并打印末端轨迹...")
    for deg in range(-90, 91, 30):
        set_joints(deg, -30, 60, 0, -30, 0)
        mujoco.mj_forward(model, data)
        ee = get_end_effector_pos()
        print(f"     joint1={deg:+4d} deg  ->  end-effector ({ee[0]:+.4f}, {ee[1]:+.4f}, {ee[2]:+.4f})")

    print("\n" + "=" * 55)
    print("  三种使用模式")
    print("=" * 55)
    print("""
  A. 交互查看:  python tests/so101_viewer.py
     鼠标旋转缩放，看机械臂结构和运动

  B. 脚本控制:  在本文件基础上写控制逻辑
     set_joints(a1,a2,a3,a4,a5,a6)  # 设置角度
     render_camera(224,224)         # 拍照
     get_end_effector_pos()         # 读末端

  C. VLA 训练全流程:
     1. 遥操作录数据 -> lerobot 格式数据集
     2. python lerobot-train.py --policy smolvla
     3. 在仿真里评估: python lerobot-eval.py
     4. 部署到真机: 同套关节命令
""")
