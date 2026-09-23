# ExpoHub 展会市场 · 小程序（uni-app）

一套代码编译出 **微信小程序 + H5 + App**。买家端 MVP：逛展会、看展品、发布采购、消息对接。

## 目录结构

```
src/
├─ pages/                # 页面
│  ├─ index/             # 首页(推荐展会 + 热门城市)
│  ├─ exhibitions/       # 展会列表 / 详情
│  ├─ booths/            # 展位详情
│  ├─ products/          # 产品列表 / 详情
│  ├─ procurements/      # 采购列表 / 详情 / 发布
│  ├─ search/            # 搜索
│  ├─ auth/              # 登录 / 注册
│  ├─ messages/          # 会话列表 / 聊天
│  ├─ exhibitor/         # 展商工作台(展位/展品/撮合)
│  ├─ organizer/         # 主办方工作台(展会/展位/报名/统计)
│  ├─ buyer/             # 买家工作台
│  └─ mine/              # 我的 / 资料 / 设置 / 报名 / 采购
├─ components/           # ExpoCard / ProductCard / ProcurementCard / SearchBar ...
├─ api/                  # 接口封装(auth/exhibition/booth/product/procurement/message...)
├─ stores/               # pinia(user)
├─ utils/request.ts      # uni.request 封装:token 注入 + 自动刷新
└─ config/index.ts       # BASE_URL 等配置
```

## 运行

```bash
npm install

# 微信小程序(开发模式,产出到 dist/dev/mp-weixin)
npm run dev:mp-weixin

# H5
npm run dev:h5

# 微信小程序(生产构建)
npm run build:mp-weixin
```

**微信开发者工具**：导入本仓库根目录即可（`project.config.json` 已通过 `miniprogramRoot`
指向 `dist/dev/mp-weixin/`，所以要先编译一次让该目录生成）。
开发期需在「详情 → 本地设置」勾选「不校验合法域名、web-view 域名、TLS 版本以及 HTTPS 证书」，
否则 `http://localhost:8002` 的请求会被拦。

## 配置

| 文件 | 项 | 说明 |
|---|---|---|
| `src/config/index.ts` | `BASE_URL` | 后端地址，**已含 `/api` 前缀**。真机预览改成电脑局域网 IP |
| `src/manifest.json` | `mp-weixin.appid` | 微信小程序 AppID，**请替换成自己小程序的** |
| `project.config.json` | `appid` / `miniprogramRoot` | 开发者工具工程配置 |

后端接口统一结构 `{ success, code, message, data }`，分页字段为 `data.list`。
登录用 JWT 双 token，请求层自动注入与刷新；401 自动跳登录页。

## 当前状态

- ✅ 买家端页面（列表 / 详情 / 表单 / 聊天 / 我的）
- ✅ 双 token 自动刷新、错误提示
- ✅ tabBar 图标已补齐（`src/static/tabbar/`）
- ⏳ 微信一键登录：后端接口未接，登录页先走账号密码
- ⏳ 展商 / 主办方管理端仅有工作台页，完整管理功能留在网页版

## 页面开发约定

新增页面时请先读 `MIGRATION_GUIDE.md`：里面写了 HTML → 小程序的标签对照、路由替换规则
（tab 页必须用 `uni.switchTab`）、接口调用姿势和样式约定。

## 已知限制

- **原生 `input` 组件不吃 padding**：只写 `padding` 不写 `height` 时，输入框内的文字会被竖向裁掉。
  全局已在 `src/App.vue` 用 `input.form-input { height: 44px }` 兜住，自定义 `input` 时注意同样补 `height`。
- **`v-model` 在小程序端有取值时序风险**：组件内 `emit('update:modelValue')` 的回写可能晚于读取。
  组件内读值请优先用 `e.detail.value`，并保留一份本地镜像值兜底（参考 `components/SearchBar.vue`）。
- 静态资源改动后需重新编译，必要时清一次开发者工具缓存，否则 tabBar 图标等不会刷新。
