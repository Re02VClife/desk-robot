"""
GPU 可用性检测脚本
用于 Phase 3 VLA 模型部署前的前置条件检查

用法: python tests/gpu_check.py
"""

import sys


def check_gpu() -> dict:
    """检测 GPU 可用性并返回报告"""
    result = {
        "cuda_available": False,
        "gpu_count": 0,
        "gpu_name": "N/A",
        "total_vram_gb": 0,
        "free_vram_gb": 0,
        "pytorch_version": "N/A",
        "recommendation": "",
    }

    # 检查 PyTorch
    try:
        import torch
        result["pytorch_version"] = torch.__version__
    except ImportError:
        result["recommendation"] = (
            "PyTorch 未安装。请先安装 PyTorch:\n"
            "  pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
        )
        return result

    import torch

    # 检查 CUDA
    if not torch.cuda.is_available():
        result["recommendation"] = (
            "未检测到 CUDA GPU。\n"
            "  - 如果有 NVIDIA 显卡，请安装 CUDA 版本的 PyTorch\n"
            "  - 如果无独显，可考虑:\n"
            "    1. 使用 Octo-Base (CPU 可跑，~2GB 内存，成功率 71.5%)\n"
            "    2. 使用云端 GPU (如 AutoDL，按小时计费)\n"
            "    3. 购买二手 GTX 3060 (~500-800 元)"
        )
        return result

    result["cuda_available"] = True
    result["gpu_count"] = torch.cuda.device_count()
    result["gpu_name"] = torch.cuda.get_device_name(0)

    # 获取显存信息
    try:
        mem_info = torch.cuda.mem_get_info(0)  # (free, total) in bytes
        free_bytes = mem_info[0]
        total_bytes = mem_info[1]
        result["free_vram_gb"] = round(free_bytes / (1024 ** 3), 2)
        result["total_vram_gb"] = round(total_bytes / (1024 ** 3), 2)
    except Exception:
        # 旧版 PyTorch 用 torch.cuda.get_device_properties
        props = torch.cuda.get_device_properties(0)
        result["total_vram_gb"] = round(props.total_mem / (1024 ** 3), 2)
        result["free_vram_gb"] = "N/A (PyTorch 版本较旧，无法获取)"

    # 推荐
    total_gb = result["total_vram_gb"]
    if total_gb >= 12:
        result["recommendation"] = (
            f"✅ {total_gb}GB 显存，可运行 smolVLA-7B（最佳效果）\n"
            f"  推荐: smolVLA-7B (成功率 87.9%) 或 smolVLA-0.5B (轻松跑)"
        )
    elif total_gb >= 6:
        result["recommendation"] = (
            f"✅ {total_gb}GB 显存，可运行 smolVLA-0.5B + LoRA 微调\n"
            f"  推荐: smolVLA-0.5B (成功率 81.4%，4GB 显存即可)"
        )
    elif total_gb >= 4:
        result["recommendation"] = (
            f"✅ {total_gb}GB 显存，刚好能跑 smolVLA-0.5B\n"
            f"  推荐: smolVLA-0.5B (成功率 81.4%)\n"
            f"  注意: LoRA 微调可能显存不足，建议 batch_size=1"
        )
    elif total_gb >= 2:
        result["recommendation"] = (
            f"⚠️ {total_gb}GB 显存较小，smolVLA-0.5B 可能不够\n"
            f"  备选: Octo-Base (2GB 可跑，成功率 71.5%)"
        )
    else:
        result["recommendation"] = (
            f"⚠️ 显存不足 ({total_gb}GB)，无法运行 VLA 模型\n"
            f"  备选: Octo-Small (CPU 可跑，但仅 29% 成功率，仅验证用)"
        )

    return result


def print_report(result: dict):
    """打印 GPU 检测报告"""
    print("=" * 60)
    print("  GPU 可用性检测报告 — 小智机械臂 VLA 项目")
    print("=" * 60)
    print()
    print(f"  PyTorch 版本:  {result['pytorch_version']}")
    print(f"  CUDA 可用:     {result['cuda_available']}")
    print(f"  GPU 数量:      {result['gpu_count']}")
    print(f"  GPU 型号:      {result['gpu_name']}")
    print(f"  总显存:        {result['total_vram_gb']} GB")
    print(f"  可用显存:      {result['free_vram_gb']} GB")
    print()
    print(f"  推荐方案:")
    print(f"  {result['recommendation']}")
    print()
    print("-" * 60)
    print("  模型显存需求参考:")
    print("    smolVLA-7B        ~16GB  成功率 87.9%")
    print("    smolVLA-0.5B      ~4GB   成功率 81.4% (推荐)")
    print("    Octo-Base         ~2GB   成功率 71.5% (备选)")
    print("    Octo-Small        <1GB   成功率 29.3% (仅验证)")
    print("=" * 60)


if __name__ == "__main__":
    report = check_gpu()
    print_report(report)

    # 返回码: 0=GPU可用, 1=不可用
    sys.exit(0 if report["cuda_available"] else 1)
