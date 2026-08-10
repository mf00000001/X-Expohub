# HelloWorld

一个极简的 **Hello World** 全栈演示项目，展示前后端分离的交互流程。

按架构师推荐，提供三种语言实现：

| 实现 | 文件 | 启动命令 | 端口 |
|------|------|----------|------|
| **FastAPI** ⭐推荐 | `main.py` | `uvicorn main:app --reload --host 0.0.0.0 --port 8000` | 8000 |
| Flask | `app_flask.py` | `flask --app app_flask run` 或 `python app_flask.py` | 5000 |
| Express | `app_express.js` | `node app_express.js` | 3000 |

## 项目结构

```
helloworld/
├── README.md                  # 项目说明文档
├── requirements.txt           # FastAPI 依赖
├── requirements-flask.txt     # Flask 依赖
├── .gitignore                 # Git 忽略规则
├── main.py                    # FastAPI 应用入口（推荐）
├── app_flask.py               # Flask 实现
├── app_express.js             # Express (Node.js) 实现
├── static/                    # 前端静态文件目录
│   ├── index.html             # 主页面
│   ├── style.css              # 样式表
│   └── app.js                 # 前端 JavaScript 逻辑
└── tests/                     # 测试目录
    └── test_hello.py          # 接口测试
```

## 快速开始

### FastAPI（推荐）

```bash
cd helloworld
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Flask

```bash
cd helloworld
pip install -r requirements-flask.txt
python app_flask.py
```

### Express

```bash
cd helloworld
npm install express
node app_express.js
```

## 访问服务

| 地址 | 说明 |
|------|------|
| http://localhost:8000/ | 前端页面（Hello World 演示） |
| http://localhost:8000/hello | API 接口（返回问候消息） |
| http://localhost:8000/api/health | 健康检查接口 |
| http://localhost:8000/docs | Swagger API 文档（仅 FastAPI） |

## API 接口

### GET /hello

返回问候消息。

**响应示例：**

```json
{
    "message": "Hello, World!"
}
```

### GET /api/health

健康检查接口。

**响应示例：**

```json
{
    "status": "ok",
    "service": "HelloWorld",
    "version": "1.0.0"
}
```

## 运行测试

```bash
pip install pytest httpx
pytest tests/ -v
```

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端框架 | FastAPI / Flask / Express | >=0.110.0 / >=3.0.0 / >=4.x |
| ASGI 服务器 | Uvicorn | >=0.27.0 |
| 前端 | HTML5 + CSS3 + Vanilla JS | — |
| 数据格式 | JSON | — |

> 不引入数据库、ORM、Redis 等中间件，保持项目极简。
