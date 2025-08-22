/**
 * 职面星火 - 通用导航栏组件
 * 统一管理所有页面的导航栏，确保一致性和易维护性
 */

class NavbarComponent {
    constructor() {
        this.userInfo = null;
        this.init();
    }

    /**
     * 初始化导航栏组件
     */
    async init() {
        await this.checkAuth();
        await this.fetchUserInfo();
        this.render();
        this.bindEvents();
    }

    /**
     * 检查用户认证状态
     */
    async checkAuth() {
        const token = localStorage.getItem('access_token');
        if (!token) {
            // 对于某些公开页面（如登录、注册），不需要强制跳转
            const publicPages = ['login.html', 'register.html', 'index.html'];
            const currentPage = window.location.pathname.split('/').pop();
            if (!publicPages.includes(currentPage)) {
                window.location.href = '/frontend/login.html';
                return;
            }
        }
    }

    /**
     * 获取用户信息
     */
    async fetchUserInfo() {
        const token = localStorage.getItem('access_token');
        if (!token) return;
        
        try {
            const resp = await fetch('/api/v1/profile', {
                headers: { 'Authorization': 'Bearer ' + token }
            });
            
            if (!resp.ok) {
                throw new Error('获取用户信息失败');
            }
            
            this.userInfo = await resp.json();
        } catch (error) {
            console.error('获取用户信息失败:', error);
            localStorage.removeItem('access_token');
            // 如果不是公开页面，跳转到登录页面
            const publicPages = ['login.html', 'register.html', 'index.html'];
            const currentPage = window.location.pathname.split('/').pop();
            if (!publicPages.includes(currentPage)) {
                window.location.href = '/frontend/login.html';
            }
        }
    }

    /**
     * 获取当前页面，用于高亮当前导航项
     */
    getCurrentPage() {
        const path = window.location.pathname;
        const page = path.split('/').pop();
        
        // 根据页面名称返回对应的导航项标识
        if (page.includes('setting_page') || page.includes('interview')) return 'interview';
        if (page.includes('assessment') || page.includes('logical') || page.includes('communication')) return 'assessment';
        if (page.includes('learning') || page.includes('course')) return 'learning';
        if (page.includes('user-profile') || page.includes('Resume') || page.includes('career')) return 'profile';
        return 'home';
    }

    /**
     * 根据当前页面位置生成正确的链接路径
     */
    getLinkPath(path) {
        const currentPath = window.location.pathname;
        
        // 如果当前在根目录（index.html），路径需要相对调整
        if (currentPath.endsWith('index.html') || currentPath === '/' || currentPath.split('/').length <= 2) {
            return `./${path}`;
        } else {
            // 如果在frontend目录下的页面，根据路径调整
            if (path.startsWith('frontend/')) {
                return `./${path.replace('frontend/', '')}`;
            } else if (path === 'index.html') {
                return '../index.html';
            } else if (path.startsWith('static/')) {
                return `../${path}`;
            }
            return `./${path}`;
        }
    }

    /**
     * 渲染导航栏HTML
     */
    render() {
        const currentPage = this.getCurrentPage();
        
        const navbarHTML = `
            <div class="bg-white shadow-sm">
                <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div class="flex justify-between items-center h-16">
                        <a href="${this.getLinkPath('index.html')}" class="flex items-center">
                            <img src="${this.getLinkPath('static/logo.png')}" alt="logo" class="h-8 w-8 mr-2 inline-block align-middle">
                            <p class="ml-2 text-lg font-medium">职面星火</p>
                        </a>
                        <nav class="flex space-x-8">
                            <a href="${this.getLinkPath('index.html')}" class="flex items-center px-3 py-2 text-sm font-medium ${currentPage === 'home' ? 'text-primary' : 'text-gray-700 hover:text-gray-900'}">
                                <div class="w-5 h-5 flex items-center justify-center mr-2">
                                    <i class="ri-home-line"></i>
                                </div>
                                首页
                            </a>
                            <a href="${this.getLinkPath('frontend/interview.html')}" class="flex items-center px-3 py-2 text-sm font-medium ${currentPage === 'interview' ? 'text-primary' : 'text-gray-700 hover:text-gray-900'}">
                                <div class="w-5 h-5 flex items-center justify-center mr-2">
                                    <i class="ri-video-chat-line"></i>
                                </div>
                                面试模拟
                            </a>
                            <a href="${this.getLinkPath('frontend/assessment-options.html')}" class="flex items-center px-3 py-2 text-sm font-medium ${currentPage === 'assessment' ? 'text-primary' : 'text-gray-700 hover:text-gray-900'}">
                                <div class="w-5 h-5 flex items-center justify-center mr-2">
                                    <i class="ri-bar-chart-line"></i>
                                </div>
                                能力评估
                            </a>
                            <a href="${this.getLinkPath('frontend/learning-resources.html')}" class="flex items-center px-3 py-2 text-sm font-medium ${currentPage === 'learning' ? 'text-primary' : 'text-gray-700 hover:text-gray-900'}">
                                <div class="w-5 h-5 flex items-center justify-center mr-2">
                                    <i class="ri-book-open-line"></i>
                                </div>
                                学习资源
                            </a>
                            <a href="${this.getLinkPath('frontend/user-profile.html')}" class="flex items-center px-3 py-2 text-sm font-medium ${currentPage === 'profile' ? 'text-primary' : 'text-gray-700 hover:text-gray-900'}">
                                <div class="w-5 h-5 flex items-center justify-center mr-2">
                                    <i class="ri-user-settings-line"></i>
                                </div>
                                个人中心
                            </a>
                        </nav>
                        <div id="navbar-user-info" class="flex items-center">
                            ${this.renderUserInfo()}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 插入导航栏到页面顶部
        const navbarContainer = document.getElementById('navbar-container');
        if (navbarContainer) {
            navbarContainer.innerHTML = navbarHTML;
        } else {
            // 如果没有专门的容器，插入到 body 开头
            document.body.insertAdjacentHTML('afterbegin', navbarHTML);
        }
    }

    /**
     * 渲染用户信息部分
     */
    renderUserInfo() {
        const token = localStorage.getItem('access_token');
        
        // 如果没有token或者没有用户信息，显示登录和注册按钮
        if (!token || !this.userInfo) {
            return `
                <div class="flex items-center space-x-3">
                    <a href="${this.getLinkPath('frontend/login.html')}" class="text-gray-700 hover:text-primary px-4 py-2 rounded-button whitespace-nowrap transition-colors">
                        登录
                    </a>
                    <a href="${this.getLinkPath('frontend/register.html')}" class="bg-primary text-white px-4 py-2 rounded-button hover:bg-opacity-90 transition-colors whitespace-nowrap">
                        注册
                    </a>
                </div>
            `;
        }

        // 显示用户信息和下拉菜单
        return `
            <div class="flex items-center">
                <div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center overflow-hidden">
                    ${this.userInfo.avatar_url ? 
                        `<img src="${this.userInfo.avatar_url}" class="w-full h-full object-cover" alt="头像">` : 
                        `<i class="ri-user-line text-white"></i>`}
                </div>
                <div class="ml-2">
                    <p class="text-sm font-medium text-gray-900">${this.userInfo.name || '未知用户'}</p>
                    <p class="text-xs text-gray-500">${this.getRoleText(this.userInfo.role)}</p>
                </div>
                <div class="ml-4 relative">
                    <button id="user-menu-btn" class="flex items-center text-gray-400 hover:text-gray-600">
                        <i class="ri-more-2-line"></i>
                    </button>
                    <div id="user-dropdown" class="hidden absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg py-1 border border-gray-200 z-50">
                        <a href="./Resume_management.html" class="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-file-text-line"></i>
                            </div>
                            简历管理
                        </a>
                        <a href="./user-profile.html" class="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-settings-line"></i>
                            </div>
                            个人设置
                        </a>
                        <div class="border-t border-gray-100"></div>
                        <button id="logout-btn" class="flex items-center w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-logout-box-line"></i>
                            </div>
                            退出登录
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * 获取用户角色文本
     */
    getRoleText(role) {
        switch(role) {
            case 'admin': return '管理员';
            case 'teacher': return '教师';
            case 'student': return '学生';
            default: return '用户';
        }
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        // 延迟绑定事件，确保DOM元素已经创建
        setTimeout(() => {
            // 用户下拉菜单 - 只在已登录时绑定
            const userMenuBtn = document.getElementById('user-menu-btn');
            const userDropdown = document.getElementById('user-dropdown');
            const logoutBtn = document.getElementById('logout-btn');

            if (userMenuBtn && userDropdown) {
                // 移除可能的旧事件监听器
                userMenuBtn.replaceWith(userMenuBtn.cloneNode(true));
                const newUserMenuBtn = document.getElementById('user-menu-btn');
                
                newUserMenuBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    userDropdown.classList.toggle('hidden');
                });

                // 点击其他地方关闭下拉菜单
                document.addEventListener('click', (e) => {
                    if (!userDropdown.contains(e.target) && !newUserMenuBtn.contains(e.target)) {
                        userDropdown.classList.add('hidden');
                    }
                });
            }

            // 退出登录
            if (logoutBtn) {
                const self = this; // 保存 this 引用
                logoutBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    if (confirm('确定要退出登录吗？')) {
                        self.clearAllCache();
                        window.location.href = '/frontend/login.html';
                    }
                });
            }

            // 导航链接点击事件处理
            const navLinks = document.querySelectorAll('#navbar-container nav a');
            navLinks.forEach(link => {
                link.addEventListener('click', function(e) {
                    const href = this.getAttribute('href');
                    if (href && (href.includes('.html') || href.startsWith('/'))) {
                        console.log('导航到:', href);
                    }
                });
            });
        }, 100);
    }

    /**
     * 更新用户信息（用于动态更新）
     */
    async updateUserInfo() {
        await this.fetchUserInfo();
        const userInfoContainer = document.getElementById('navbar-user-info');
        if (userInfoContainer) {
            userInfoContainer.innerHTML = this.renderUserInfo();
            this.bindEvents(); // 重新绑定事件
        }
    }

    /**
     * 清除所有本地缓存数据
     */
    clearAllCache() {
        try {
            // 清除 localStorage 中的所有认证和用户相关数据
            const keysToRemove = [
                'access_token',
                'refresh_token', 
                'current_user',
                'userInfo',
                'user_profile',
                'chat_sessions',
                'interview_data',
                'assessment_results',
                'learning_progress'
            ];

            // 删除指定的 localStorage 项目
            keysToRemove.forEach(key => {
                localStorage.removeItem(key);
            });

            // 清除 sessionStorage 中的所有数据
            sessionStorage.clear();

            // 重置组件内部状态
            this.userInfo = null;

            console.log('✅ 所有本地缓存已清除');
        } catch (error) {
            console.error('清除缓存时出错:', error);
        }
    }

    /**
     * 静态方法：初始化导航栏
     */
    static init() {
        return new NavbarComponent();
    }
}

// 自动初始化（当DOM加载完成时）
document.addEventListener('DOMContentLoaded', function() {
    NavbarComponent.init();
});

// 导出供其他脚本使用
window.NavbarComponent = NavbarComponent;
