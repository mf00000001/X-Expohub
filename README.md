# ExpoHub — 展会撮合平台

展前撮合引擎：帮犹豫展商免费试水 → 看到数据 → 参加线下展会。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + SQLAlchemy + SQLite + JWT |
| 前端 | Vue 3 + TypeScript + Vite + Pinia |
| 数据 | 1000微展位 · 10027展品 · 18行业分类 |

## 快速启动

### 1. 后端
```bash
cd expohub-backend
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```
后端运行在 http://localhost:8002

### 2. 前端
```bash
cd expo-hub-frontend
npm install
npx vite --host 0.0.0.0 --port 5173
```
前端运行在 http://localhost:5173

### 3. 测试账号
| 角色 | 用户名 | 密码 |
|------|--------|------|
| 管理员 | admin | admin123 |
| 展商 | exhibitor_huawei | exh123 |
| 买家 | buyer_li | buyer123 |
| 游客 | visitor_chen | visitor123 |
| 主办方 | organizer_canton | org123 |

## 重建数据库
```bash
cd expohub-backend
rm -f expohub.db
python3 seed.py        # 基础数据
python3 gen_products.py # 生成10000展品
```

## 项目结构
```
expohub-backend/          # FastAPI 后端
  app/
    api/                  # 22个API模块
    models/               # 15个数据模型
    core/                 # 配置/安全/权限
  seed.py                 # 种子数据
  gen_products.py         # 展品生成器

expo-hub-frontend/        # Vue 3 前端
  src/
    views/                # 60+页面组件
    api/                  # 15个API模块
    components/           # 15个复用组件
    router/               # 路由配置
    stores/               # Pinia状态管理
```
