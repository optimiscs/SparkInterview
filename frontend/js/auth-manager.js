/**
 * 简化认证管理器
 * 只负责用户认证状态管理
 */
class AuthManager {
    constructor() {
        this.currentUser = null;
    }

    /**
     * 初始化 - 检查认证状态和获取用户数据
     */
    async init() {
        console.log('🔧 初始化认证管理器...');
        
        // 检查本地存储的认证信息
        const token = localStorage.getItem('access_token');
        const userData = localStorage.getItem('current_user');
        
        if (!token) {
            console.log('⚠️ 未找到认证token');
            return { authenticated: false, reason: 'no_token' };
        }

        if (userData) {
            try {
                this.currentUser = JSON.parse(userData);
                console.log('✅ 本地用户信息已加载:', this.currentUser.name);
            } catch (e) {
                console.warn('⚠️ 解析本地用户信息失败');
            }
        }

        // 验证token有效性
        try {
            const isValid = await this.validateToken();
            if (isValid) {
                return { authenticated: true, user: this.currentUser };
            } else {
                return { authenticated: false, reason: 'invalid_token' };
            }
        } catch (error) {
            console.error('❌ 认证初始化失败:', error);
            return { authenticated: false, reason: 'auth_error', error };
        }
    }

    /**
     * 验证Token有效性
     */
    async validateToken() {
        const token = localStorage.getItem('access_token');
        if (!token) return false;

        try {
            console.log('🔐 验证token有效性...');
            const response = await fetch('/api/v1/profile', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                const userInfo = await response.json();
                this.currentUser = userInfo;
                // 更新本地存储
                localStorage.setItem('current_user', JSON.stringify(userInfo));
                console.log('✅ Token验证成功');
                return true;
            } else {
                console.error('❌ Token验证失败:', response.status);
                this.clearAuth();
                return false;
            }
        } catch (error) {
            console.error('❌ Token验证异常:', error);
            return false;
        }
    }







    /**
     * 清除认证信息
     */
    clearAuth() {
        localStorage.removeItem('access_token');
        localStorage.removeItem('current_user');
        localStorage.removeItem('user_info');
        this.currentUser = null;
        console.log('🧹 认证信息已清除');
    }

    /**
     * 获取认证头
     */
    getAuthHeaders() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            throw new Error('认证token缺失');
        }
        
        return {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        };
    }

    // Getters
    get isAuthenticated() {
        return !!(this.currentUser && localStorage.getItem('access_token'));
    }

    get user() {
        return this.currentUser;
    }
}

// 全局实例
window.authManager = new AuthManager();

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = AuthManager;
}
