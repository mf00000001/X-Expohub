# HelloWorld 项目技术方案

> 版本：v1.0  
> 作者：Architect Agent  
> 日期：2025-01-18

---

## 📋 需求理解

构建一个极简的"Hello World"全栈演示项目。后端使用 FastAPI 提供 `/hello` 接口返回 JSON 消息，前端使用纯 HTML + CSS + JavaScript 页面通过 fetch 调用该接口并展示返回结果。项目用于演示前后端分离的交互流程，适合作为入门教学或快速原型。

---

## ❓ 待澄清问题

无，需求清晰明确。

---

## 🏗️ 技术方案

### 整体架构

采用**前后端分离的单体架构**：

```
┌──────────────┐      HTTP/JSON      ┌──────────────┐
│   Frontend   │  ──────────────────>  │   Backend    │
│ (HTML/CSS/JS)│  <──────────────────  │  (FastAPI)   │
└──────────────┘       Response        └──────────────┘
```

- 前端：纯静态页面，通过 `fetch` API 调用后端接口
- 后端：FastAPI 单进程服务，提供 RESTful API
- 通信：HTTP + JSON
- 部署：后端通过 `uvicorn` 启动，前端由后端以静态文件方式托管（也可独立部署）

### 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **后端框架** | FastAPI | ≥0.110.0 | 高性能异步 Web 框架 |
| **ASGI 服务器** | Uvicorn | ≥0.27.0 | 轻量级 ASGI 服务器 |
| **前端** | HTML5 + CSS3 + Vanilla JS | — | 纯原生，无框架依赖 |
| **数据格式** | JSON | — | 接口数据交换格式 |
| **包管理** | pip + venv | — | Python 虚拟环境 |

> 不引入数据库、ORM、Redis 等中间件，保持项目极简。

### 数据模型

本项目无数据库，数据模型仅包含接口响应结构：

**Response Body** (`GET /hello`)

```json
{
  "message": "Hello, World!"
}
```

对应的 Pydantic 模型：

```python
from pydantic import BaseModel

class HelloResponse(BaseModel):
    message: str
```

### API 设计

| 方法 | 路径 | 描述 | 请求参数 | 响应 |
|------|------|------|----------|------|
| `GET` | `/hello` | 返回问候消息 | 无 | `{"message": "Hello, World!"}` |
| `GET` | `/` | 健康检查 | 无 | `{"status": "ok", "service": "HelloWorld"}` |

**响应状态码：**
- `200 OK` — 成功返回

### 文件结构

```
helloworld/
├── README.md                  # 项目说明文档
├── requirements.txt           # Python 依赖清单
├── .gitignore                 # Git 忽略规则
├── main.py                    # FastAPI 应用入口（含路由和静态文件托管）
├── static/                    # 前端静态文件目录
│   ├── index.html             # 主页面
│   ├── style.css              # 样式表
│   └── app.js                 # 前端 JavaScript 逻辑
└── tests/                     # 测试目录
    └── test_hello.py          # 接口测试
```

### 关键代码设计

#### 1. 后端入口 `main.py`

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="HelloWorld", version="1.0.0")


# ========== 数据模型 ==========

class HelloResponse(BaseModel):
    message: str


# ========== API 路由 ==========

@app.get("/", tags=["health"])
async def root():
    """健康检查"""
    return {"status": "ok", "service": "HelloWorld", "version": "1.0.0"}


@app.get("/hello", response_model=HelloResponse, tags=["hello"])
async def say_hello():
    """
    返回 Hello World 问候消息
    
    Returns:
        HelloResponse: 包含问候消息的 JSON 对象
    """
    return HelloResponse(message="Hello, World!")


# ========== 托管静态文件（前端页面） ==========

app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

#### 2. 前端页面 `static/index.html`

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hello World</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div class="container">
        <h1>🌍 Hello World</h1>
        <button id="greetBtn" class="btn">点击问候</button>
        <div id="result" class="result hidden">
            <span id="messageText"></span>
        </div>
        <div id="error" class="error hidden">
            <span>⚠️ 请求失败：</span><span id="errorText"></span>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>
```

#### 3. 样式表 `static/style.css`

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #333;
}

.container {
    background: white;
    padding: 2.5rem 3rem;
    border-radius: 16px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
    text-align: center;
    max-width: 420px;
    width: 90%;
}

h1 {
    font-size: 2rem;
    margin-bottom: 1.5rem;
    color: #2d3748;
}

.btn {
    background: #667eea;
    color: white;
    border: none;
    padding: 12px 32px;
    font-size: 1.1rem;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
}

.btn:hover {
    background: #5a6fd6;
}

.btn:active {
    transform: scale(0.97);
}

.btn:disabled {
    background: #a0aec0;
    cursor: not-allowed;
}

.result {
    margin-top: 1.5rem;
    padding: 1rem;
    background: #f0fff4;
    border: 1px solid #68d391;
    border-radius: 8px;
    font-size: 1.3rem;
    font-weight: 600;
    color: #276749;
}

.error {
    margin-top: 1.5rem;
    padding: 1rem;
    background: #fff5f5;
    border: 1px solid #fc8181;
    border-radius: 8px;
    font-size: 1rem;
    color: #c53030;
}

.hidden {
    display: none;
}
```

#### 4. 前端逻辑 `static/app.js`

```javascript
/**
 * HelloWorld 前端交互逻辑
 * 通过 fetch 调用后端 /hello 接口并展示结果
 */

document.addEventListener('DOMContentLoaded', () => {
    const greetBtn = document.getElementById('greetBtn');
    const resultDiv = document.getElementById('result');
    const errorDiv = document.getElementById('error');
    const messageText = document.getElementById('messageText');
    const errorText = document.getElementById('errorText');

    /**
     * 调用 /hello 接口并更新 UI
     */
    async function fetchGreeting() {
        // 重置状态
        resultDiv.classList.add('hidden');
        errorDiv.classList.add('hidden');
        greetBtn.disabled = true;
        greetBtn.textContent = '请求中...';

        try {
            const response = await fetch('/hello', {
                method: 'GET',
                headers: {
                    'Accept': 'application/json',
                },
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            // 显示成功结果
            messageText.textContent = data.message;
            resultDiv.classList.remove('hidden');
        } catch (err) {
            // 显示错误信息
            errorText.textContent = err.message;
            errorDiv.classList.remove('hidden');
        } finally {
            greetBtn.disabled = false;
            greetBtn.textContent = '点击问候';
        }
    }

    greetBtn.addEventListener('click', fetchGreeting);
});
```

#### 5. 测试 `tests/test_hello.py`

```python
"""
HelloWorld API 测试

使用 FastAPI 的 TestClient 进行接口测试
"""

import pytest
from fastapi.testclient import TestClient
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
        """测试根路径健康检查"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "HelloWorld"
```

---

## 📝 任务拆解

| 序号 | 任务 | 负责人 | 预估时间 | 依赖 | 优先级 |
|------|------|--------|---------|------|--------|
| 1 | 创建项目目录结构和 `.gitignore` | Backend | 5min | — | P0 |
| 2 | 编写 `requirements.txt` 依赖清单 | Backend | 2min | — | P0 |
| 3 | 实现 `main.py` — FastAPI 应用 + `/hello` 接口 + 静态文件托管 | Backend | 20min | 1, 2 | P0 |
| 4 | 实现 `static/index.html` — 页面结构 | Frontend | 15min | — | P0 |
| 5 | 实现 `static/style.css` — 页面样式 | Frontend | 15min | — | P0 |
| 6 | 实现 `static/app.js` — 前端 fetch 调用逻辑 | Frontend | 20min | — | P0 |
| 7 | 实现 `tests/test_hello.py` — 接口自动化测试 | Testing | 15min | 3 | P1 |
| 8 | 编写 `README.md` — 项目说明和启动指南 | Docs | 10min | 3, 4, 5, 6 | P1 |
| 9 | 手动端到端验证（启动服务 → 打开页面 → 点击按钮） | QA | 10min | 3, 4, 5, 6 | P1 |

### 依赖关系图

```
1 (目录) ──> 3 (main.py) ──> 7 (测试)
2 (依赖) ──> 3 (main.py)
4 (HTML) ──> 9 (端到端验证)
5 (CSS)  ──> 9 (端到端验证)
6 (JS)   ──> 9 (端到端验证)
8 (README) ──> 所有实现任务
```

---

## ⚠️ 风险与建议

### 风险

| 风险 | 等级 | 说明 | 应对措施 |
|------|------|------|----------|
| 端口冲突 | 🟡 低 | 8000 端口可能被其他服务占用 | 在启动命令中指定 `--port 8001` 或使用环境变量 |
| 静态文件路径 | 🟢 极低 | 路由 `/` 与静态文件挂载可能冲突 | 确保 `StaticFiles` 挂载在路由注册之后，且设置 `html=True` |
| CORS 问题 | 🟢 极低 | 前端页面由后端托管，同源无跨域 | 如果前端独立部署，需添加 `CORSMiddleware` |

### 建议

1. **启动方式**（推荐使用 uvicorn 直接启动）：
   ```bash
   # 安装依赖
   pip install -r requirements.txt
   
   # 启动服务（热重载模式，开发用）
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **访问方式**：
   - 前端页面：`http://localhost:8000/`
   - API 接口：`http://localhost:8000/hello`
   - API 文档：`http://localhost:8000/docs`（FastAPI 自动生成 Swagger UI）
   - 健康检查：`http://localhost:8000/`

3. **运行测试**：
   ```bash
   pip install pytest httpx
   pytest tests/ -v
   ```

4. **扩展方向**（如需）：
   - 添加更多问候语言：`GET /hello?lang=zh` 返回中文问候
   - 添加 POST 接口：`POST /hello` 接受自定义名字
   - 添加数据库：引入 SQLite 记录问候次数
   - 前端升级：引入 Vue.js 或 React 构建 SPA

---

## ✅ 验收标准

| 编号 | 验收项 | 预期结果 |
|------|--------|----------|
| 1 | 启动服务 | uvicorn 正常启动，无报错 |
| 2 | 访问根路径 | 浏览器打开显示 Hello World 页面 |
| 3 | 点击"点击问候"按钮 | 页面展示 "Hello, World!" 消息 |
| 4 | 访问 `GET /hello` | 返回 `{"message": "Hello, World!"}`，状态码 200 |
| 5 | 访问 `GET /` | 返回健康检查 JSON |
| 6 | 运行测试 | `pytest tests/ -v` 全部通过 |
| 7 | API 文档 | 访问 `/docs` 显示 Swagger 文档页面 |
