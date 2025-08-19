/**
 * 简历数据管理器
 * 负责简历的CRUD操作、列表渲染、预览等核心功能
 */
class ResumeDataManager {
    constructor() {
        this.currentResumeId = null;
        this.resumesList = [];
        this.isInitialized = false;
        
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.loadResumesList();
        
        console.log('✅ 简历数据管理器初始化完成');
    }
    
    // ==================== API调用函数 ====================
    
    async callAPI(endpoint, method = 'GET', data = null) {
        try {
            const url = `/api/v1/resume${endpoint}`;
            console.log('API调用:', method, url, data);
            
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('access_token') || ''}`
                }
            };

            if (data && method !== 'GET') {
                options.body = JSON.stringify(data);
            }

            const response = await fetch(url, options);
            console.log('API响应状态:', response.status, response.statusText);
            
            if (!response.ok) {
                let errorData = {};
                try {
                    errorData = await response.json();
                } catch (e) {
                    console.error('解析错误响应失败:', e);
                }
                const errorMessage = errorData.detail || errorData.message || `HTTP ${response.status}: ${response.statusText}`;
                console.error('API错误:', errorMessage, errorData);
                throw new Error(errorMessage);
            }

            const result = await response.json();
            console.log('API调用成功:', result);
            return result;
        } catch (error) {
            console.error('API调用失败:', error);
            throw error;
        }
    }
    
    // ==================== 简历列表管理 ====================
    
    async loadResumesList() {
        const loadingEl = document.getElementById('resumeListLoading');
        const emptyEl = document.getElementById('resumeListEmpty');
        const errorEl = document.getElementById('resumeListError');

        try {
            // 显示加载状态
            loadingEl?.classList.remove('hidden');
            emptyEl?.classList.add('hidden');
            errorEl?.classList.add('hidden');

            const response = await this.callAPI('/list');
            
            if (response.success && response.data) {
                this.resumesList = response.data;
                this.renderResumesList(this.resumesList);
                
                // 如果有简历，默认加载第一个
                if (this.resumesList.length > 0) {
                    await this.loadResumeDetail(this.resumesList[0].id);
                } else {
                    this.showResumePreviewEmpty();
                }
            } else {
                this.showResumeListEmpty();
            }
        } catch (error) {
            console.error('加载简历列表失败:', error);
            this.showResumeListError();
        } finally {
            loadingEl?.classList.add('hidden');
        }
    }
    
    renderResumesList(resumes) {
        const listContainer = document.getElementById('resumeVersionsList');
        const loadingEl = document.getElementById('resumeListLoading');
        const emptyEl = document.getElementById('resumeListEmpty');
        const errorEl = document.getElementById('resumeListError');

        // 隐藏所有状态
        loadingEl?.classList.add('hidden');
        emptyEl?.classList.add('hidden');
        errorEl?.classList.add('hidden');

        if (resumes.length === 0) {
            emptyEl?.classList.remove('hidden');
            return;
        }

        // 清除现有内容（保留状态元素）
        const existingItems = listContainer?.querySelectorAll('.version-item');
        existingItems?.forEach(item => item.remove());

        // 渲染简历项目
        resumes.forEach((resume, index) => {
            const resumeItem = this.createResumeListItem(resume, index);
            listContainer?.appendChild(resumeItem);
        });
    }
    
    createResumeListItem(resume, index) {
        const resumeItem = document.createElement('div');
        resumeItem.className = `version-item ${index === 0 ? 'bg-primary/5 border border-primary/20' : 'hover:bg-gray-50'} rounded-lg p-3 cursor-pointer`;
        resumeItem.dataset.resumeId = resume.id;

        const updatedAt = this.formatDate(resume.updated_at);
        const statusBadge = resume.status === 'draft' ? 
            '<span class="text-xs text-yellow-600 bg-yellow-50 px-2 py-1 rounded-full">草稿</span>' :
            (index === 0 ? '<span class="text-xs text-primary bg-primary/10 px-2 py-1 rounded-full">当前</span>' : '');

        resumeItem.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex-1" data-resume-content>
                    <div class="flex items-center justify-between">
                        <span class="text-sm font-medium text-gray-900">${resume.version_name || '未命名简历'}</span>
                        ${statusBadge}
                    </div>
                    <p class="text-xs text-gray-500 mt-1">
                        ${resume.target_position ? `${resume.target_position} · ` : ''}最后修改：${updatedAt}
                    </p>
                </div>
                <div class="resume-actions hidden ml-2 flex items-center space-x-1">
                    <button class="edit-resume-btn p-1 text-gray-400 hover:text-blue-600 rounded transition-colors" 
                            data-resume-id="${resume.id}" 
                            title="编辑简历">
                        <i class="ri-edit-line text-xs"></i>
                    </button>
                    <button class="delete-resume-btn p-1 text-gray-400 hover:text-red-600 rounded transition-colors" 
                            data-resume-id="${resume.id}" 
                            data-resume-name="${resume.version_name || '未命名简历'}"
                            title="删除简历">
                        <i class="ri-delete-bin-line text-xs"></i>
                    </button>
                </div>
            </div>
        `;

        this.bindResumeItemEvents(resumeItem, resume);
        return resumeItem;
    }
    
    bindResumeItemEvents(resumeItem, resume) {
        // 添加悬停效果显示操作按钮
        resumeItem.addEventListener('mouseenter', function() {
            const actions = this.querySelector('.resume-actions');
            if (actions) actions.classList.remove('hidden');
        });

        resumeItem.addEventListener('mouseleave', function() {
            const actions = this.querySelector('.resume-actions');
            if (actions) actions.classList.add('hidden');
        });

        // 添加点击事件（只对内容区域有效）
        const contentArea = resumeItem.querySelector('[data-resume-content]');
        contentArea.addEventListener('click', async (e) => {
            e.stopPropagation();
            
            // 更新视觉状态
            document.querySelectorAll('.version-item').forEach(item => {
                item.classList.remove('bg-primary/5', 'border-primary/20');
                item.classList.add('hover:bg-gray-50');
                const badge = item.querySelector('.text-primary.bg-primary\\/10');
                if (badge) badge.remove();
            });

            resumeItem.classList.remove('hover:bg-gray-50');
            resumeItem.classList.add('bg-primary/5', 'border-primary/20');
            
            const titleDiv = contentArea.querySelector('.flex.items-center.justify-between');
            const existingBadge = titleDiv.querySelector('.text-primary.bg-primary\\/10');
            if (!existingBadge && resume.status !== 'draft') {
                const currentBadge = document.createElement('span');
                currentBadge.className = 'text-xs text-primary bg-primary/10 px-2 py-1 rounded-full';
                currentBadge.textContent = '当前';
                titleDiv.appendChild(currentBadge);
            }

            // 加载简历详情
            await this.loadResumeDetail(resume.id);
        });

        // 添加编辑按钮事件
        const editBtn = resumeItem.querySelector('.edit-resume-btn');
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.editResume(resume.id);
        });

        // 添加删除按钮事件
        const deleteBtn = resumeItem.querySelector('.delete-resume-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showDeleteConfirmDialog(resume.id, resume.version_name || '未命名简历');
        });
    }
    
    // ==================== 简历详情管理 ====================
    
    async loadResumeDetail(resumeId) {
        const contentEl = document.getElementById('resumePreviewContent');
        const loadingEl = document.getElementById('resumePreviewLoading');
        const emptyEl = document.getElementById('resumePreviewEmpty');
        const errorEl = document.getElementById('resumePreviewError');

        try {
            // 验证resumeId的有效性
            if (!resumeId || resumeId === 'undefined' || resumeId === 'null') {
                console.error('❌ 无效的简历ID:', resumeId);
                this.currentResumeId = null;
                this.showResumePreviewEmpty();
                return null;
            }

            console.log('📋 设置当前简历ID:', resumeId);
            this.currentResumeId = resumeId;
            
            // 显示加载状态
            contentEl?.classList.add('hidden');
            emptyEl?.classList.add('hidden');
            errorEl?.classList.add('hidden');
            loadingEl?.classList.remove('hidden');

            const response = await this.callAPI(`/detail/${resumeId}`);
            
            if (response.success && response.data) {
                this.renderResumePreview(response.data);
                console.log('✅ 简历详情加载成功，currentResumeId:', this.currentResumeId);
                
                // 通知分析器加载对应的分析结果
                if (window.resumeAnalyzer) {
                    window.resumeAnalyzer.loadResumeAnalysis(resumeId);
                }
                
                return response.data;
            } else {
                throw new Error('获取简历详情失败');
            }
        } catch (error) {
            console.error('❌ 加载简历详情失败:', error);
            this.currentResumeId = null;
            this.showResumePreviewError();
            return null;
        } finally {
            loadingEl?.classList.add('hidden');
        }
    }
    
    renderResumePreview(resumeData) {
        const contentEl = document.getElementById('resumePreviewContent');
        const loadingEl = document.getElementById('resumePreviewLoading');
        const emptyEl = document.getElementById('resumePreviewEmpty');
        const errorEl = document.getElementById('resumePreviewError');

        // 隐藏其他状态
        loadingEl?.classList.add('hidden');
        emptyEl?.classList.add('hidden');
        errorEl?.classList.add('hidden');

        // 构建简历HTML
        const basicInfo = resumeData.basic_info || {};
        const education = resumeData.education || {};
        const projects = resumeData.projects || [];
        const skills = resumeData.skills || {};
        const internship = resumeData.internship || [];

        const resumeHTML = `
            <!-- 个人信息 -->
            <div class="text-center mb-8">
                <h1 class="text-3xl font-bold text-gray-900 mb-2">${basicInfo.name || '姓名'}</h1>
                <div class="flex justify-center items-center space-x-6 text-gray-600 flex-wrap">
                    ${basicInfo.phone ? `
                        <span class="flex items-center">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-phone-line"></i>
                            </div>
                            ${basicInfo.phone}
                        </span>
                    ` : ''}
                    ${basicInfo.email ? `
                        <span class="flex items-center">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-mail-line"></i>
                            </div>
                            ${basicInfo.email}
                        </span>
                    ` : ''}
                    ${basicInfo.github ? `
                        <span class="flex items-center">
                            <div class="w-4 h-4 flex items-center justify-center mr-2">
                                <i class="ri-github-line"></i>
                            </div>
                            ${basicInfo.github}
                        </span>
                    ` : ''}
                </div>
            </div>

            ${education.school ? `
            <!-- 教育背景 -->
            <div class="mb-8">
                <h2 class="text-xl font-bold text-gray-900 mb-4 border-b-2 border-primary pb-2">教育背景</h2>
                <div class="space-y-4">
                    <div>
                        <div class="flex justify-between items-start">
                            <div>
                                <h3 class="font-semibold text-gray-900">${education.school}</h3>
                                <p class="text-gray-600">${education.major || ''} ${education.degree ? '| ' + education.degree : ''}</p>
                            </div>
                            ${education.startTime && education.endTime ? `
                                <span class="text-gray-500">${education.startTime} - ${education.endTime}</span>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
            ` : ''}

            ${projects.length > 0 ? `
            <!-- 项目经历 -->
            <div class="mb-8">
                <h2 class="text-xl font-bold text-gray-900 mb-4 border-b-2 border-primary pb-2">项目经历</h2>
                <div class="space-y-6">
                    ${projects.map(project => `
                        <div class="project-item">
                            <div class="flex justify-between items-start mb-2">
                                <h3 class="font-semibold text-gray-900">${project.name || '项目名称'}</h3>
                                ${project.time ? `<span class="text-gray-500">${project.time}</span>` : ''}
                            </div>
                            ${project.techStack ? `<p class="text-gray-600 mb-2">技术栈：${project.techStack}</p>` : ''}
                            ${project.description ? `
                                <div class="text-gray-700">
                                    ${project.description.split('\n').map(line => 
                                        line.trim() ? `<p class="mb-1">${line.startsWith('•') ? line : '• ' + line}</p>` : ''
                                    ).join('')}
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}

            ${internship.length > 0 ? `
            <!-- 实习经历 -->
            <div class="mb-8">
                <h2 class="text-xl font-bold text-gray-900 mb-4 border-b-2 border-primary pb-2">实习经历</h2>
                <div class="space-y-6">
                    ${internship.map(exp => `
                        <div class="internship-item">
                            <div class="flex justify-between items-start mb-2">
                                <div>
                                    <h3 class="font-semibold text-gray-900">${exp.company || '公司名称'}</h3>
                                    <p class="text-gray-600">${exp.position || '职位名称'}</p>
                                </div>
                                ${exp.period ? `<span class="text-gray-500">${exp.period}</span>` : ''}
                            </div>
                            ${exp.description ? `
                                <div class="text-gray-700">
                                    ${exp.description.split('\n').map(line => 
                                        line.trim() ? `<p class="mb-1">${line.startsWith('•') ? line : '• ' + line}</p>` : ''
                                    ).join('')}
                                </div>
                            ` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}

            ${Object.keys(skills).length > 0 ? `
            <!-- 技能清单 -->
            <div class="mb-8">
                <h2 class="text-xl font-bold text-gray-900 mb-4 border-b-2 border-primary pb-2">技能清单</h2>
                <div class="grid grid-cols-2 gap-4">
                    ${skills.programmingLanguages ? `
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">编程语言</h4>
                            <p class="text-gray-700">${skills.programmingLanguages}</p>
                        </div>
                    ` : ''}
                    ${skills.frontend ? `
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">前端技术</h4>
                            <p class="text-gray-700">${skills.frontend}</p>
                        </div>
                    ` : ''}
                    ${skills.backend ? `
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">后端技术</h4>
                            <p class="text-gray-700">${skills.backend}</p>
                        </div>
                    ` : ''}
                    ${skills.database ? `
                        <div>
                            <h4 class="font-semibold text-gray-900 mb-2">数据库</h4>
                            <p class="text-gray-700">${skills.database}</p>
                        </div>
                    ` : ''}
                </div>
            </div>
            ` : ''}
        `;

        if (contentEl) {
            contentEl.innerHTML = resumeHTML;
            contentEl.classList.remove('hidden');
        }
        
        // 通知分析管理器简历已切换
        if (window.resumeAnalyzer && typeof window.resumeAnalyzer.onResumeChanged === 'function') {
            setTimeout(() => {
                window.resumeAnalyzer.onResumeChanged(resumeData.id);
            }, 100); // 稍微延迟以确保DOM已更新
        }
    }
    
    // ==================== 简历操作 ====================
    
    editResume(resumeId) {
        if (!resumeId) {
            this.showErrorMessage('简历ID无效');
            return;
        }
        window.location.href = `./Resume_create.html?id=${resumeId}&action=edit`;
    }
    
    async deleteResume(resumeId) {
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        const deleteText = document.getElementById('deleteButtonText');
        const deleteLoading = document.getElementById('deleteButtonLoading');

        try {
            // 显示加载状态
            if (deleteBtn) deleteBtn.disabled = true;
            if (deleteText) deleteText.classList.add('hidden');
            if (deleteLoading) deleteLoading.classList.remove('hidden');

            const response = await this.callAPI(`/delete/${resumeId}`, 'DELETE');
            
            if (response.success) {
                // 隐藏对话框
                this.hideDeleteConfirmDialog();
                
                // 显示成功消息
                this.showSuccessMessage('简历删除成功');
                
                // 如果删除的是当前预览的简历，清空预览区域
                if (this.currentResumeId === resumeId) {
                    this.currentResumeId = null;
                    this.showResumePreviewEmpty();
                }
                
                // 重新加载简历列表
                await this.loadResumesList();
            } else {
                throw new Error(response.message || '删除失败');
            }
        } catch (error) {
            console.error('删除简历失败:', error);
            this.showErrorMessage(error.message || '简历删除失败，请稍后重试');
            
            // 重置按钮状态
            if (deleteBtn) deleteBtn.disabled = false;
            if (deleteText) deleteText.classList.remove('hidden');
            if (deleteLoading) deleteLoading.classList.add('hidden');
        }
    }
    
    // ==================== 删除确认对话框 ====================
    
    showDeleteConfirmDialog(resumeId, resumeName) {
        this.currentDeleteResumeId = resumeId;
        const dialog = document.getElementById('deleteConfirmDialog');
        const nameDisplay = document.getElementById('deleteResumeNameDisplay');
        
        if (nameDisplay) nameDisplay.textContent = `"${resumeName}"`;
        if (dialog) dialog.classList.remove('hidden');
    }

    hideDeleteConfirmDialog() {
        const dialog = document.getElementById('deleteConfirmDialog');
        const deleteBtn = document.getElementById('confirmDeleteBtn');
        const deleteText = document.getElementById('deleteButtonText');
        const deleteLoading = document.getElementById('deleteButtonLoading');
        
        if (dialog) dialog.classList.add('hidden');
        if (deleteBtn) deleteBtn.disabled = false;
        if (deleteText) deleteText.classList.remove('hidden');
        if (deleteLoading) deleteLoading.classList.add('hidden');
        this.currentDeleteResumeId = null;
    }
    
    // ==================== 状态显示函数 ====================
    
    showResumeListEmpty() {
        document.getElementById('resumeListLoading')?.classList.add('hidden');
        document.getElementById('resumeListEmpty')?.classList.remove('hidden');
        document.getElementById('resumeListError')?.classList.add('hidden');
        this.showResumePreviewEmpty();
    }

    showResumeListError() {
        document.getElementById('resumeListLoading')?.classList.add('hidden');
        document.getElementById('resumeListEmpty')?.classList.add('hidden');
        document.getElementById('resumeListError')?.classList.remove('hidden');
        this.showResumePreviewError();
    }

    showResumePreviewEmpty() {
        document.getElementById('resumePreviewContent')?.classList.add('hidden');
        document.getElementById('resumePreviewLoading')?.classList.add('hidden');
        document.getElementById('resumePreviewEmpty')?.classList.remove('hidden');
        document.getElementById('resumePreviewError')?.classList.add('hidden');
    }

    showResumePreviewError() {
        document.getElementById('resumePreviewContent')?.classList.add('hidden');
        document.getElementById('resumePreviewLoading')?.classList.add('hidden');
        document.getElementById('resumePreviewEmpty')?.classList.add('hidden');
        document.getElementById('resumePreviewError')?.classList.remove('hidden');
    }
    
    // ==================== 事件绑定 ====================
    
    bindEvents() {
        // 重试加载简历列表
        const retryLoadResumeBtn = document.getElementById('retryLoadResumes');
        if (retryLoadResumeBtn) {
            retryLoadResumeBtn.addEventListener('click', () => this.loadResumesList());
        }

        // 重试加载简历详情
        const retryLoadDetailBtn = document.getElementById('retryLoadResumeDetail');
        if (retryLoadDetailBtn) {
            retryLoadDetailBtn.addEventListener('click', () => {
                if (this.currentResumeId) {
                    this.loadResumeDetail(this.currentResumeId);
                }
            });
        }

        // 删除确认对话框事件
        document.getElementById('closeDeleteDialog')?.addEventListener('click', () => this.hideDeleteConfirmDialog());
        document.getElementById('cancelDeleteBtn')?.addEventListener('click', () => this.hideDeleteConfirmDialog());
        document.getElementById('confirmDeleteBtn')?.addEventListener('click', () => {
            if (this.currentDeleteResumeId) {
                this.deleteResume(this.currentDeleteResumeId);
            }
        });

        // 点击对话框外部关闭
        document.getElementById('deleteConfirmDialog')?.addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                this.hideDeleteConfirmDialog();
            }
        });
    }
    
    // ==================== 辅助函数 ====================
    
    formatDate(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('zh-CN');
        } catch (error) {
            return dateString;
        }
    }
    
    showSuccessMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'fixed top-6 right-6 bg-green-50 text-green-800 px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2';
        messageDiv.innerHTML = `
            <div class="w-5 h-5 flex items-center justify-center">
                <i class="ri-check-line text-green-600"></i>
            </div>
            <span>${message}</span>
        `;
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 3000);
    }

    showErrorMessage(message) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'fixed top-6 right-6 bg-red-50 text-red-800 px-6 py-3 rounded-lg shadow-lg z-50 flex items-center space-x-2';
        messageDiv.innerHTML = `
            <div class="w-5 h-5 flex items-center justify-center">
                <i class="ri-close-line text-red-600"></i>
            </div>
            <span>${message}</span>
        `;
        document.body.appendChild(messageDiv);
        
        setTimeout(() => {
            if (messageDiv.parentNode) {
                messageDiv.remove();
            }
        }, 4000);
    }
    
    // ==================== 公共API ====================
    
    getCurrentResumeId() {
        return this.currentResumeId;
    }
    
    refreshResumesList() {
        return this.loadResumesList();
    }
}

// 导出供其他模块使用
if (typeof window !== 'undefined') {
    window.ResumeDataManager = ResumeDataManager;
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { ResumeDataManager };
}
