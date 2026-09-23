# ExpoHub 桌面启动器

把 ExpoHub 变成一个**双击即用的桌面应用**，同时保留开发时的实时热更新。

## 用法

| 桌面图标 | 作用 |
|---|---|
| **ExpoHub** | 启动前后端 + 打开应用窗口（已在运行则只开窗，不重复启动） |
| **ExpoHub 控制台** | 状态面板：实时显示服务状态，含 打开应用 / 启动服务 / 停止服务 / 打开日志目录 |

重新创建桌面图标：

```powershell
powershell -ExecutionPolicy Bypass -File desktop\install-shortcuts.ps1
# 加 -IncludeStop 会额外生成一个 "ExpoHub 停止" 图标
```

## 热更新是怎么成立的

关键在于**应用窗口加载的是源码实时服务，不是打包产物**：

| 层 | 机制 | 改代码后的表现 |
|---|---|---|
| 前端 | Vite dev server（HMR） | 保存 `.vue` / `.ts` → 浏览器秒级生效，无需刷新 |
| 后端 | uvicorn `--reload` | 保存 `.py` → 进程自动重启，几秒内生效 |

所以**改完代码不需要重新打包**，桌面上的应用永远是最新代码。

> 对比：如果用 PyInstaller 把后端冻成 exe、前端 build 成静态文件，就得到一个真正的独立软件，但代码被冻进二进制——每次改动都要重新打包，两者不可兼得。

## 文件说明

```
desktop/
├── start.ps1              启动：拉起前后端 + 健康检查 + 开窗（核心逻辑）
├── start.vbs              静默入口（无黑框闪烁），桌面图标指向它
├── stop.ps1 / stop.vbs    停止前后端
├── console.ps1 / .vbs     状态控制台（WinForms，无额外依赖）
├── install-shortcuts.ps1  创建桌面快捷方式（幂等）
├── lib/common.ps1         共享库：路径常量 / 日志 / 端口与 HTTP 探测 / 进程控制
├── assets/make_icon.py    生成图标（Pillow 多尺寸 .ico）
├── assets/expohub.ico     图标成品
└── logs/                  运行日志（已 gitignore）
```

## 手动调试

```powershell
# 前台启动，能看到完整过程输出
powershell -ExecutionPolicy Bypass -File desktop\start.ps1

# 强制重启（先停再起）
powershell -ExecutionPolicy Bypass -File desktop\start.ps1 -Restart

# 只起服务不开窗
powershell -ExecutionPolicy Bypass -File desktop\start.ps1 -NoBrowser

# 停止
powershell -ExecutionPolicy Bypass -File desktop\stop.ps1
```

## 日志

| 文件 | 内容 |
|---|---|
| `logs/launcher.log` | 启动器自身：启停过程、健康检查结果、错误 |
| `logs/backend.err.log` | **后端实际输出在这里**（uvicorn 日志走 stderr） |
| `logs/backend.out.log` | 后端应用的 `print()` |
| `logs/frontend.out.log` | 前端 Vite 输出 |
| `logs/frontend.err.log` | 前端 stderr（通常为空） |

`launcher.log` 超过 1MB 自动轮转为 `.log.1`。

## 排障

启动失败时脚本会**弹窗并附上日志末尾内容**，按提示处理即可。常见情况：

| 现象 | 原因与处理 |
|---|---|
| 弹窗提示"端口 8002 已被占用，但它不是 ExpoHub 后端" | 别的程序占了端口。弹窗里会给出占用进程的 PID 和名字，结束它或改端口 |
| 弹窗提示"Vite 未安装" | `cd expo-hub-frontend && npm install` |
| 弹窗提示"Python 解释器不存在" | `scripts\setup_env.bat` 重建虚拟环境 |
| 应用窗口没出现 | 没装 Edge 会回退默认浏览器；若都没有，手动开 http://localhost:5173 |

## 设计要点（改代码前先看）

1. **所有 `.ps1` 必须是 UTF-8 with BOM**。PowerShell 5.1 默认按 ANSI 读脚本，没有 BOM 会让中文全变乱码。
   重新编码：
   ```powershell
   $b = New-Object System.Text.UTF8Encoding($true)
   Get-ChildItem desktop -Recurse -Filter *.ps1 | ForEach-Object {
       [IO.File]::WriteAllText($_.FullName, [IO.File]::ReadAllText($_.FullName, [Text.UTF8Encoding]::new($false)), $b)
   }
   ```
2. **`.vbs` 必须纯 ASCII**。wscript 按 ANSI 读，中文会乱码。
3. **健康检查用 HTTP 而不是端口存活判断**。uvicorn 先 bind socket 再跑 startup，端口开了不等于应用能用。
4. **`console.vbs` 用隐藏方式启动时必须显式 `ShowWindow`**。`WScript.Shell.Run(cmd, 0, ...)` 的 SW_HIDE 会写进进程 STARTUPINFO，Windows 会把这套隐藏状态套到该进程创建的第一个顶层窗口上——WinForms 窗体正好中招，表现为进程活着但句柄为 0、`ShowDialog` 永久阻塞。`console.ps1` 里用 P/Invoke 显式覆盖了它。
5. **停止服务必须杀进程树**（`taskkill /T`）。uvicorn `--reload` 是"父进程持 socket + 子进程跑应用"，只杀父会留下孤儿监听。
6. **控件宽度是按 9pt 微软雅黑实测的**，不是拍的。改文案后请复测：
   ```powershell
   $f = New-Object Drawing.Font('Microsoft YaHei UI', 9)
   $g = [Drawing.Graphics]::FromImage((New-Object Drawing.Bitmap(1,1)))
   $g.MeasureString('要测的文字', $f).Width   # 与控件 Width 比较
   ```
