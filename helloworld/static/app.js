/**
 * HelloWorld 前端交互逻辑
 *
 * 功能：
 * - 点击按钮通过 fetch 调用 /hello 接口
 * - 展示返回的 message 或错误信息
 * - 支持重试操作
 * - 加载、成功、错误三种状态切换
 * - 键盘可访问性（Enter/Space 触发按钮）
 */

(function () {
    'use strict';

    // =============================================
    // DOM 元素引用
    // =============================================

    const elements = {
        greetBtn: document.getElementById('greetBtn'),
        retryBtn: document.getElementById('retryBtn'),
        loading: document.getElementById('loading'),
        result: document.getElementById('result'),
        error: document.getElementById('error'),
        messageText: document.getElementById('messageText'),
        errorText: document.getElementById('errorText'),
        statusText: document.getElementById('statusText'),
    };

    // 验证所有元素是否存在
    const missingElements = Object.entries(elements)
        .filter(([, el]) => !el)
        .map(([key]) => key);

    if (missingElements.length > 0) {
        console.error(
            `[HelloWorld] 缺少必要 DOM 元素: ${missingElements.join(', ')}`
        );
        return;
    }

    // =============================================
    // 状态管理
    // =============================================

    /** 当前是否正在请求中 */
    let isLoading = false;

    /** 上次请求成功的数据（用于重试后对比） */
    let lastSuccessData = null;

    // =============================================
    // UI 更新函数
    // =============================================

    /**
     * 隐藏所有状态面板
     */
    function hideAllStates() {
        elements.loading.classList.add('hidden');
        elements.result.classList.add('hidden');
        elements.error.classList.add('hidden');
    }

    /**
     * 显示加载状态
     */
    function showLoading() {
        hideAllStates();
        elements.loading.classList.remove('hidden');
        elements.greetBtn.disabled = true;
        elements.greetBtn.querySelector('.btn__text').textContent = '请求中...';
        elements.statusText.textContent = '请求中';
    }

    /**
     * 显示成功结果
     * @param {string} message - 服务端返回的问候消息
     */
    function showSuccess(message) {
        hideAllStates();
        elements.messageText.textContent = message;
        elements.result.classList.remove('hidden');
        elements.greetBtn.disabled = false;
        elements.greetBtn.querySelector('.btn__text').textContent = '点击问候';
        elements.statusText.textContent = '就绪';
        lastSuccessData = message;
    }

    /**
     * 显示错误信息
     * @param {string} errorMsg - 错误描述
     */
    function showError(errorMsg) {
        hideAllStates();
        elements.errorText.textContent = errorMsg;
        elements.error.classList.remove('hidden');
        elements.greetBtn.disabled = false;
        elements.greetBtn.querySelector('.btn__text').textContent = '点击问候';
        elements.statusText.textContent = '出错';
    }

    // =============================================
    // 核心业务逻辑
    // =============================================

    /**
     * 调用 /hello 接口获取问候消息
     *
     * 使用 AbortController 支持超时控制，
     * 通过 Accept 头声明期望 JSON 响应。
     */
    async function fetchGreeting() {
        // 防止重复请求
        if (isLoading) return;
        isLoading = true;

        showLoading();

        /** 5 秒超时控制 */
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 5000);

        try {
            const response = await fetch('/hello', {
                method: 'GET',
                headers: {
                    Accept: 'application/json',
                },
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            // 处理非 2xx 状态码
            if (!response.ok) {
                let detail = `HTTP ${response.status}`;
                try {
                    const errorBody = await response.json();
                    if (errorBody.detail) {
                        detail = errorBody.detail;
                    }
                } catch {
                    // 非 JSON 响应，使用状态文本
                    detail = response.statusText || detail;
                }
                throw new Error(detail);
            }

            // 解析 JSON 响应
            const data = await response.json();

            // 验证响应数据结构
            if (!data || typeof data.message !== 'string') {
                throw new Error('服务端返回数据格式异常');
            }

            showSuccess(data.message);
        } catch (err) {
            clearTimeout(timeoutId);

            // 区分错误类型，给出友好提示
            let userMessage = '';

            if (err.name === 'AbortError') {
                userMessage = '请求超时，请检查网络连接后重试';
            } else if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
                userMessage = '无法连接到服务器，请确认服务是否启动';
            } else if (err.message) {
                userMessage = err.message;
            } else {
                userMessage = '发生未知错误，请稍后重试';
            }

            showError(userMessage);
        } finally {
            isLoading = false;
        }
    }

    /**
     * 重试操作：复用 fetchGreeting 逻辑
     */
    function retryFetch() {
        fetchGreeting();
    }

    // =============================================
    // 事件绑定
    // =============================================

    // 主按钮点击
    elements.greetBtn.addEventListener('click', fetchGreeting);

    // 重试按钮点击
    elements.retryBtn.addEventListener('click', retryFetch);

    // =============================================
    // 键盘可访问性支持
    // =============================================

    /**
     * 为按钮添加键盘支持（Enter / Space）
     * 原生 <button> 已支持，但这里额外处理自定义交互
     */
    elements.greetBtn.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            fetchGreeting();
        }
    });

    elements.retryBtn.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            retryFetch();
        }
    });

    // =============================================
    // 初始化日志
    // =============================================

    console.log('[HelloWorld] 前端应用已就绪 🚀');
    console.log('[HelloWorld] 接口地址: GET /hello');
})();
