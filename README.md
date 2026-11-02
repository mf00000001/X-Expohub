# ExpoHub — 展会撮合平台

展前撮合引擎：帮犹豫展商免费试水 → 看到数据 → 参加线下展会。

## 技术栈

| 层 | 技术 |
|---|------|
| 后端 | FastAPI + SQLAlchemy + SQLite + JWT（4 角色：visitor / buyer / exhibitor / admin） |
| 前端 | Vue 3 + TypeScript + Vite + Pinia（平台自营展会管理在 `/admin/*`） |
| 数据 | 1000微展位 · 10027展品 · 18行业分类 |

## 一键启动（推荐）

**Windows：双击根目录的 `start_all.bat`**　　**macOS / Linux：`./scripts/start_all.sh`**

脚本会自动完成：装依赖（首次）→ 检查端口 → 起后端 → 起前端 → 打开浏览器。

| 项目 | 地址 |
|---|---|
| 前端页面 | http://127.0.0.1:5173 |
| 接口文档 | http://127.0.0.1:8002/docs |
| 接口根路径 | http://127.0.0.1:8002 |

- 首次运行会自动创建 `.venv`、安装后端依赖与前端 `npm install`（约 2-4 分钟），之后再启动是秒级。
- 后端、前端各开一个窗口，标题分别是 `ExpoHub-Backend` / `ExpoHub-Frontend`；关掉窗口即停止对应服务。
- **停止服务**：双击 `stop_all.bat`（macOS/Linux 用 `./scripts/stop_all.sh`），或直接关掉两个服务窗口。
- 若服务已在运行，重复双击 `start_all.bat` 会自动复用（不会报端口冲突），只重新打开浏览器。

可选参数（Windows 追加在命令后；macOS/Linux 用对应的 `--no-browser` 等）：

| 参数 | 作用 |
|---|---|
| `-NoBrowser` | 不自动打开浏览器 |
| `-Reload` | 后端开启 `--reload` 热重载（改后端代码自动重启） |
| `-Background` | 不弹新窗口，日志写入 `logs\`（自检/CI 用） |
| `-BindHost 0.0.0.0` | 允许局域网/手机访问（默认只监听本机 127.0.0.1） |
| `-BackendPort 8002` / `-FrontendPort 5173` | 修改端口 |
| `-SkipInstall` | 跳过依赖检查，直接启动 |

> 底层脚本：`scripts/start_all.ps1`、`scripts/stop_all.ps1`（UTF-8 with BOM，PowerShell 5.1/7 均可运行）。

## 手动启动（分步）

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
| 平台管理员（展会自营） | admin | admin123 |
| 平台运营子账号（原「主办方」，角色已升级为 admin） | organizer_canton | org123 |
| 展商 | exhibitor_huawei | exh123 |
| 买家 | buyer_li | buyer123 |
| 游客/观众 | visitor_chen | visitor123 |

> 2026-10-19 起为**两方撮合**：展商 ↔ 采购商；会展举办方（organizer）角色已取消，展会由平台自营，
> 创建/发布展会、展位分配、报名名单、票种、现场核销都归平台管理员（路由 `/admin/*`）。

## 在另一台电脑运行（一键复现环境）

> 👉 **最省事的方式**：换台电脑后直接双击 `start_all.bat`（macOS/Linux 用 `./scripts/start_all.sh`），它会从零创建 `.venv`、安装前后端依赖并启动，等价于下面所有步骤。下面的分步方式适合需要单独调试某一端时使用。

> 说明：本仓库**不包含**虚拟环境本身（`.venv` 和 `.env` 都被 git 忽略——因为 venv 硬编码了本机路径与系统，直接拷贝到别的电脑通常会报错）。这里提供的是**从零复现**同一套环境的一键方案，保证跨电脑可用。

### 后端（FastAPI + SQLite）

**方式一：一键脚本**

- Windows：双击运行 `scripts\setup_env.bat`
- macOS / Linux：`./scripts/setup_env.sh`

**方式二：手动**

```bash
cd expohub-backend
python -m venv ../.venv
# Windows          -- activate: ..\.venv\Scripts\activate
# macOS / Linux    -- activate: source ../.venv/bin/activate
pip install -r requirements.txt
```

**启动后端**（http://localhost:8002）：

- Windows：`scripts\run_backend.bat`
- macOS / Linux：`./scripts/run_backend.sh`
- 或手动：`cd expohub-backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload`

> 后端依赖为**固定版本**（`expohub-backend/requirements.txt` 由已验证可运行的虚拟环境导出），保证不同电脑上复现结果一致。

### 前端（Vue 3 + Vite）

```bash
cd expo-hub-frontend
npm install
npx vite --host 0.0.0.0 --port 5173
```

### 环境要求

| 组件 | 要求 |
|------|------|
| Python | 3.12 / 3.13（已在 3.12.13 上验证；`requirements.txt` 为固定版本，过新的 Python 可能缺预编译轮子） |
| Node.js / npm | 18+（前端，已在 Node 24 / npm 11 上验证） |

> `start_all.bat` 在创建 `.venv` 时会优先挑选 `py -3.13` / `py -3.12`，找不到再退回 PATH 上的 `python`；某个版本装不上依赖会自动换下一个。


## 重建数据库
```bash
cd expohub-backend
rm -f expohub.db
python3 seed.py        # 基础数据
python3 gen_products.py # 生成10000展品
```

## 项目结构
```
scripts/
  migrate_drop_organizer.py  # 去掉主办方角色的数据迁移（幂等、带 --dry-run）
  scrape/expo_scraper.py     # 展会公开信息采集骨架（默认不联网、不落库）

expohub-backend/          # FastAPI 后端
  app/
    api/                  # 22个API模块
    models/               # 15个数据模型
    core/                 # 配置/安全/权限
  seed.py                 # 种子数据
  gen_products.py         # 展品生成器

expo-hub-frontend/        # Vue 3 前端
  src/
    views/                # 58 个页面组件
    views/expo-admin/     # 平台自营展会管理（原 organizer 页面）
    api/                  # 15个API模块
    components/           # 15个复用组件
    router/               # 路由配置
    stores/               # Pinia状态管理

expo-hub-miniapp/         # 微信小程序（原生，含登录/展会/采购/通知）
expo-hub-uniapp/          # uni-app 端（vue3+vite，可编译 mp-weixin）
desktop/                  # Windows 桌面启动器（GUI，健康检查 + 一键启停）
portable/                 # 便携包构建（免安装 exe 分发）
docs/                     # 架构、合规、决策记录（archive/ 为历史交付物）
```
