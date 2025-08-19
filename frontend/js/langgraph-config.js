/**
 * LangGraph接口配置 - 简化版本
 * 基础的API端点和配置管理
 */

const LANGGRAPH_CONFIG = {
    // 基础配置
    BASE_URL: window.location.origin,
    API_PREFIX: '/api/v1',
    
    // LangGraph接口端点
    ENDPOINTS: {
        // 会话管理
        START_CHAT: '/langgraph-chat/start',
        SEND_MESSAGE: '/langgraph-chat/message', 
        STREAM_MESSAGE: '/langgraph-chat/stream',
        GET_SESSIONS: '/langgraph-chat/sessions',
        DELETE_SESSION: '/langgraph-chat/sessions',
        
        // 状态管理
        SESSION_STATUS: '/langgraph-chat/sessions',  // /{session_id}/status
        RESET_SESSION: '/langgraph-chat/sessions',   // /{session_id}/reset
        
        // 系统监控
        HEALTH_CHECK: '/langgraph-chat/health',
        
        // WebSocket
        WEBSOCKET: '/langgraph-chat/ws'  // /{session_id}
    },
    
    // 请求配置
    REQUEST_CONFIG: {
        timeout: 30000,  // 30秒超时
        retries: 3,      // 重试3次
        headers: {
            'Content-Type': 'application/json'
        }
    },
    
    // WebSocket配置 - 简化版本
    WEBSOCKET_CONFIG: {
        reconnectInterval: 5000,
        maxReconnectAttempts: 3
    }
};

/**
 * 构建完整的API URL
 */
function buildApiUrl(endpoint, pathParams = {}) {
    let url = LANGGRAPH_CONFIG.BASE_URL + LANGGRAPH_CONFIG.API_PREFIX + LANGGRAPH_CONFIG.ENDPOINTS[endpoint];
    
    // 替换路径参数
    for (const [key, value] of Object.entries(pathParams)) {
        url = url.replace(`{${key}}`, value);
    }
    
    return url;
}

/**
 * 构建WebSocket URL
 */
function buildWebSocketUrl(sessionId) {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${wsProtocol}//${window.location.host}${LANGGRAPH_CONFIG.API_PREFIX}${LANGGRAPH_CONFIG.ENDPOINTS.WEBSOCKET}/${sessionId}`;
}

/**
 * 获取认证头 - 简化版本
 */
function getAuthHeaders() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        throw new Error('认证令牌缺失，请先登录');
    }
    
    return {
        ...LANGGRAPH_CONFIG.REQUEST_CONFIG.headers,
        'Authorization': `Bearer ${token}`
    };
}

/**
 * 标准化API调用 - 简化版本
 */
async function callLangGraphAPI(endpoint, options = {}) {
    const url = buildApiUrl(endpoint, options.pathParams);
    
    const requestOptions = {
        method: options.method || 'GET',
        headers: getAuthHeaders(),
        ...LANGGRAPH_CONFIG.REQUEST_CONFIG
    };
    
    if (options.body) {
        requestOptions.body = JSON.stringify(options.body);
    }
    
    console.log(`🔗 调用LangGraph API: ${requestOptions.method} ${url}`);
    
    try {
        const response = await fetch(url, requestOptions);
        
        if (!response.ok) {
            let errorData;
            try {
                errorData = await response.json();
            } catch (parseError) {
                errorData = { detail: response.statusText };
            }
            
            console.error(`❌ API错误 ${response.status}:`, errorData.detail);
            
            throw new Error(`API调用失败: ${response.status} ${errorData.detail || '未知错误'}`);
        }
        
        const data = await response.json();
        console.log(`✅ API调用成功: ${endpoint}`);
        return data;
        
    } catch (error) {
        console.error(`❌ API调用失败: ${endpoint}`, error.message);
        throw error;
    }
}

/**
 * 基础状态映射 - 简化版本
 */
const STATUS_MAPPING = {
    emotions: {
        'neutral': '中性',
        'anxious': '紧张',
        'confident': '自信',
        'confused': '困惑'
    },
    
    actions: {
        'ask_question': '询问信息',
        'provide_comfort': '情感支持',
        'generate_question': '生成问题',
        'update_database': '更新数据'
    }
};

// 导出配置供其他模块使用
if (typeof window !== 'undefined') {
    window.LANGGRAPH_CONFIG = LANGGRAPH_CONFIG;
    window.buildApiUrl = buildApiUrl;
    window.buildWebSocketUrl = buildWebSocketUrl;
    window.callLangGraphAPI = callLangGraphAPI;
    window.getAuthHeaders = getAuthHeaders;
    window.STATUS_MAPPING = STATUS_MAPPING;
}

// CommonJS导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        LANGGRAPH_CONFIG,
        buildApiUrl,
        buildWebSocketUrl,
        callLangGraphAPI,
        getAuthHeaders,
        STATUS_MAPPING
    };
}
