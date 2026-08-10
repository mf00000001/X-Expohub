"""
HelloWorld API 测试

使用 FastAPI 的 TestClient 进行接口测试
"""

import pytest
from fastapi.testclient import TestClient

# 将上级目录加入 sys.path，使 main 模块可导入
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app

client = TestClient(app)


class TestHelloAPI:
    """Hello 接口测试"""

    def test_hello_success(self):
        """测试 GET /hello 返回正确的问候消息"""
        response = client.get("/hello")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"] == "Hello, World!"

    def test_hello_response_type(self):
        """测试响应体结构符合预期"""
        response = client.get("/hello")
        data = response.json()
        # 验证字段类型
        assert isinstance(data["message"], str)

    def test_health_check(self):
        """测试健康检查接口"""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "HelloWorld"
        assert data["version"] == "1.0.0"

    def test_health_check_fields(self):
        """测试健康检查响应字段类型"""
        response = client.get("/api/health")
        data = response.json()
        assert isinstance(data["status"], str)
        assert isinstance(data["service"], str)
        assert isinstance(data["version"], str)
