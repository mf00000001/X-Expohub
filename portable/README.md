# ExpoHub 便携试用包

把 ExpoHub 打成一个**双击即用**的绿色包，发给不会装环境的人试用。

对方**不需要**装 Python / Node / Docker / MySQL，也**不需要联网**——解压、双击、等几秒，应用窗口自己弹出来。

> 与 [`desktop/`](../desktop/README.md) 的区别：
> `desktop/` 是**给开发者自己用**的桌面启动器，依赖本机的 `.venv` 和 `node_modules`，还带热更新；
> `portable/` 是**发给外人**的独立分发包，自带 Python 运行时，代价是没有热更新（改代码要重新出包）。

---

## 目录结构

```
portable/
├── app/                        # 会被打进包里的运行时文件（源，不是产物）
│   ├── portable_main.py        # 同源托管入口：一个端口同时供前端页面与 /api
│   ├── .env.template           # 便携版环境变量模板（不含任何 API Key）
│   └── scripts/
│       ├── start.ps1           # 启动器：选端口 → 起服务 → 健康检查 → 开窗口
│       ├── stop.ps1            # 停止（杀进程树）
│       ├── update.ps1          # 从配置的更新源拉新后端代码
│       └── update-source.txt   # 更新源地址（留空 = 不启用，不影响使用）
└── build/                      # 构建与验证脚本
    ├── build_portable.ps1      # ★ 主入口：全量可复现构建
    ├── clean_demo_data.py      # 复制开发库并清理演示数据（绝不碰源库）
    ├── make_guide.py           # 生成《使用说明.docx》
    ├── make_package.ps1        # 打包 ZIP（正斜杠条目）
    ├── bom_fix.ps1             # 把 .ps1 统一转 UTF-8 with BOM
    ├── verify_business.py      # 业务链路验证（登录 / 智能匹配 / 各域抽查）
    ├── test_launcher.ps1       # 启停器端到端测试（编码规则 / 端口避让 / 幂等 / 启停）
    ├── test_acceptance.ps1     # 最终验收：解压 ZIP → 双击 → 窗口自动弹出 → 停止
    ├── test_update.ps1         # 更新链路测试（本地 HTTP 模拟源，含失败回滚，不需要 Gitee 账号）
    └── run_full_verify.ps1     # 起服务 + 业务验证 + 停止，带计时（比验收轻，适合快速回归）
```

---

## 构建

```powershell
# 全量重建（约 3–5 分钟）
powershell -ExecutionPolicy Bypass -File portable\build\build_portable.ps1

# 只重新复刻代码/数据/文档并打包（最快，改完脚本或后端代码后出包用这个）
powershell -ExecutionPolicy Bypass -File portable\build\build_portable.ps1 -SkipDeps -SkipFrontend

# 换输出目录
powershell -ExecutionPolicy Bypass -File portable\build\build_portable.ps1 -OutRoot D:\某处
```

默认工作区 `D:\Projects\expo-hub-portable`，产物 `ExpoHub-试用版.zip` 落在那里。

**发出去之前跑一遍验收**（会真的解压并弹窗口）：

```powershell
powershell -ExecutionPolicy Bypass -File portable\build\test_acceptance.ps1
```

### 四个测试各管一段

| 脚本 | 验什么 | 开销 |
|---|---|---|
| `test_launcher.ps1` | 编码规则（`.bat` 纯 ASCII / `.ps1` 带 BOM）、端口避让、重复启动不重建进程、启停干净 | 快，不开窗口 |
| `run_full_verify.ps1` | 起服务 + 登录/智能匹配/各业务域抽查 + 停止，带耗时 | 中，不开窗口 |
| `test_acceptance.ps1` | **完整领导路径**：解压 ZIP 到中文目录 → 双击 `.bat` → 窗口自动弹出 → 停止 | 慢（~2 分钟），会弹窗口 |
| `test_update.ps1` | 更新链路：本地 HTTP 模拟源做成功/404/畸形包三种情形，验证备份、回滚与失败后自动恢复 | 慢，不开窗口 |

改了后端代码后至少跑 `run_full_verify.ps1`；改了启停脚本或打包流程就跑全套。
**`test_update.ps1` 不需要 Gitee 账号**，它在本地起 HTTP 服务模拟更新源。

---

## 关键设计决策（改之前先读）

### 1. 前端与 API 同源，单进程

`portable_main.py` 让 FastAPI 在**同一个端口**既提供前端页面、又提供 `/api`。
前端 `dist` 里用的是相对路径 `/api/...`，同源后**零 CORS、零代理、零端口配置**，只起一个进程。

### 2. 不改动仓库源码

同源托管逻辑全在包内的 `app/portable_main.py`，它 `import` 未改动的 `app.main:app`，
再叠加上静态托管与 `/api/health`。因此 **git 拉取最新代码不会与它冲突**，
`expohub-backend/app/` 保持纯净。

### 3. 用绿色包而不是 PyInstaller 单文件 exe

单文件 exe 是杀软误报重灾区（360/火绒/Defender 全中）。发给领导，一旦弹「发现威胁」，
轻则他不敢点，重则以为你发了病毒。`python.exe + .py 源码 + .bat` 这种组合几乎不误报。
另外出问题时绿色包能让对方把 `logs/` 发回来定位，exe 冻死了只能靠猜。

### 4. 演示数据在副本上清理

`clean_demo_data.py` 只写**目标副本**，源库 `expohub-backend/expohub.db` 一个字节都不动
（删数据不可逆，源库是开发用的）。清理后做孤儿扫描，反复迭代直到不再产生新孤儿——
手工列级联表必然遗漏，实测漏过两次。

---

## 踩过的坑（都已在代码里注释）

| 坑 | 症状 | 处理 |
|---|---|---|
| **`.ps1` 无 BOM** | PS 5.1 按 ANSI 读，中文乱码 + 语法解析失败 | 一律 UTF-8 with BOM，`bom_fix.ps1` 兜底 |
| **`.bat` 带中文** | cmd 按 OEM 代码页读，乱码 | `.bat` 保持纯 ASCII，中文全放 `.ps1` |
| **端口探测假阳性** | Windows 允许 `127.0.0.1:P` 叠加在已占用的 `0.0.0.0:P` 上，误判"端口空闲"→ 挑了被占端口 → 服务起不来 | 必须绑 `0.0.0.0` + `ExclusiveAddressUse=$true` |
| **逐端口查端口表** | `Get-NetTCPConnection` 单次约 1.3s，探 9 个端口白等 12s（首启 16.3s → 4.8s） | 用绑定探测（毫秒级），禁止放循环里 |
| **ZIP 条目带反斜杠** | .NET Framework 的 `CreateFromDirectory` 用路径分隔符写条目名，7-Zip 解压出畸形文件名 | 手工建条目，强制 `/` |
| **失败弹窗卡死自动化** | `MessageBox` 阻塞等点击 | 脚本留 `-NoDialog` 开关 |
| **当前目录在待删目录内** | `Remove-Item -Recurse` 报"拒绝访问"。Windows 不允许删除任何进程的 CWD，而这个报错极易被误判成杀软拦截或句柄未释放（实测重试 12 秒也没用） | 删之前 `Set-Location` 出去；别养成 `Set-Location` 进临时目录的习惯 |
| **argparse 参数写错风格** | 给 python 传 `-OutDir`（PowerShell 风格）会被当成未知短选项直接报错 | 必须写 `--out-dir` |
| **jieba 体积** | 42MB，其中 `lac_small`/`posseg`/`analyse` 后端从不 import | 裁剪到 8MB；**裁完必须跑 `verify_business.py`**，确认 `textkit._JIEBA_OK=True` 且分词未退化成二元组 |

---

## 更新机制

包内 `scripts/update-source.txt` 填一个代码压缩包直链即可启用「检查更新.bat」：

```
https://gitee.com/<用户名>/<仓库>/repository/archive/master.zip
```

- **留空 = 不启用**，完全不影响正常使用
- 只替换**后端代码**（`server/app`）。前端是 Vite 编译产物，改前端必须重新出包
- 更新前自动备份到 `server/app.bak-<时间戳>`，失败自动回滚
- 推荐 Gitee：本机 `github.com` 不可直连

---

## 包体参考

| | 大小 |
|---|---|
| 解压后 | ~96 MB |
| **ZIP（发出去的）** | **~36 MB** |
| 其中 Python 运行时 + 依赖 | ~88 MB |

微信发送无压力（远低于 100MB 限制）。
