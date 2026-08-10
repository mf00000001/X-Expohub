/**
 * HelloWorld Express 实现
 *
 * 启动方式: node app_express.js
 * 依赖安装: npm install express
 */

const app = require("express")();

// 根路径 - Hello World
app.get("/", (req, res) => res.json({ message: "Hello, World!" }));

// 健康检查
app.get("/api/health", (req, res) =>
    res.json({
        status: "ok",
        service: "HelloWorld-Express",
        version: "1.0.0",
    })
);

// 启动服务
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 HelloWorld Express 服务已启动: http://localhost:${PORT}`);
    console.log(`   API: http://localhost:${PORT}/`);
    console.log(`   健康检查: http://localhost:${PORT}/api/health`);
});
