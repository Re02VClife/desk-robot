"""
pytest 共享夹具和配置

使用方式：
    pytest tests/ -v
    pytest tests/ -v -k "test_vla"  # 按名称过滤
"""
import os
import pytest


# ---- 服务器地址配置（通过环境变量覆盖）----

@pytest.fixture(scope="session")
def openclaw_host():
    """OpenClaw 服务器地址"""
    return os.environ.get("OPENCLAW_HOST", "localhost")


@pytest.fixture(scope="session")
def openclaw_ws_port():
    """OpenClaw WebSocket 端口"""
    return int(os.environ.get("OPENCLAW_WS_PORT", "8000"))


@pytest.fixture(scope="session")
def openclaw_http_port():
    """OpenClaw HTTP 端口"""
    return int(os.environ.get("OPENCLAW_HTTP_PORT", "8003"))


@pytest.fixture(scope="session")
def vla_host():
    """VLA 推理服务地址"""
    return os.environ.get("VLA_HOST", "localhost")


@pytest.fixture(scope="session")
def vla_port():
    """VLA 推理服务端口"""
    return int(os.environ.get("VLA_PORT", "8080"))


@pytest.fixture(scope="session")
def ws_url(openclaw_host, openclaw_ws_port):
    """WebSocket 完整 URL"""
    return f"ws://{openclaw_host}:{openclaw_ws_port}"


@pytest.fixture(scope="session")
def vla_url(vla_host, vla_port):
    """VLA 服务完整 URL"""
    return f"http://{vla_host}:{vla_port}"


# ---- 跳过标记 ----

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line("markers", "requires_hardware: 需要 ESP32 + 机械臂硬件在线")
    config.addinivalue_line("markers", "requires_gpu: 需要 GPU")
    config.addinivalue_line("markers", "requires_server: 需要 OpenClaw 服务器运行")
    config.addinivalue_line("markers", "slow: 耗时测试")
