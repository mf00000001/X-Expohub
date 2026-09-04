"""
pytest 共享夹具：测试数据库隔离

在导入任何 app.* 模块之前把 DATABASE_URL 指向独立测试库，
避免测试污染开发库 expohub.db。每次运行前重置测试库文件。
"""
import os

_TEST_DB = os.environ.get("TEST_DATABASE_URL", "sqlite:///./pytest_expohub.db")

# 必须在 import app.* 之前设置（Settings 于导入时读取环境变量）
os.environ["DATABASE_URL"] = _TEST_DB

# AI 相关测试假定「无真实密钥 → mock 降级」：剥离开发者 .env 里的真实密钥配置，
# 避免本机接入智谱后这些用例误连真实网关（与 DATABASE_URL 同款隔离手法）
for _k in ("AI_PROVIDER", "AI_MODEL", "AI_API_KEY", "DEEPSEEK_API_KEY",
           "SILICONFLOW_API_KEY", "OPENAI_COMPAT_API_KEY", "OPENAI_COMPAT_BASE_URL"):
    os.environ.pop(_k, None)
os.environ["AI_PROVIDER"] = "mock"

# 重置测试库（引擎尚未创建，此时删除安全）
if _TEST_DB.startswith("sqlite"):
    _f = _TEST_DB.split("///")[-1]
    if os.path.exists(_f):
        os.remove(_f)

