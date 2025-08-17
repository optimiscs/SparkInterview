/**
 * 简历管理页面 JavaScript
 * 负责处理简历列表、AI分析、数据管理等功能
 */

class ResumeManagement {
    constructor() {
        this.currentResumeId = null;
        this.resumesList = [];
        this.currentAnalysisId = null;
        this.analysisPollingInterval = null;
        
        this.init();
    }

    async init() {
        console.log('简历管理页面初始化开始');
        
        // 绑定事件
        this.bindEvents();
        
        // 加载简历列表
        await this.loadResumesList();
        
        // 确保消息提示函数存在
        this.ensureMessageFunctions();
        
        console.log('简历管理页面初始化完成');
        console.log('使用 debugResumeAnalysis() 查看调试信息');
    }

    // API调用函数
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

    // 获取简历列表
    async loadResumesList() {
        const loadingEl = document.getElementById('resumeListLoading');
        const emptyEl = document.getElementById('resumeListEmpty');
        const errorEl = document.getElementById('resumeListError');

        try {
            // 显示加载状态
            if (loadingEl) loadingEl.classList.remove('hidden');
            if (emptyEl) emptyEl.classList.add('hidden');
            if (errorEl) errorEl.classList.add('hidden');

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
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    }

    // 渲染简历列表
    renderResumesList(resumes) {
        const listContainer = document.getElementById('resumeVersionsList');
        const loadingEl = document.getElementById('resumeListLoading');
        const emptyEl = document.getElementById('resumeListEmpty');
        const errorEl = document.getElementById('resumeListError');

        if (!listContainer) return;

        // 隐藏所有状态
        if (loadingEl) loadingEl.classList.add('hidden');
        if (emptyEl) emptyEl.classList.add('hidden');
        if (errorEl) errorEl.classList.add('hidden');

        if (resumes.length === 0) {
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }

        // 清除现有内容（保留状态元素）
        const existingItems = listContainer.querySelectorAll('.version-item');
        existingItems.forEach(item => item.remove());

        // 渲染简历项目
        resumes.forEach((resume, index) => {
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

            // 绑定事件
            this.bindResumeItemEvents(resumeItem, resume, index);
            
            listContainer.appendChild(resumeItem);
        });
    }

    // 绑定简历项目事件
    bindResumeItemEvents(resumeItem, resume, index) {
        // 悬停效果
        resumeItem.addEventListener('mouseenter', function() {
            const actions = this.querySelector('.resume-actions');
            if (actions) actions.classList.remove('hidden');
        });

        resumeItem.addEventListener('mouseleave', function() {
            const actions = this.querySelector('.resume-actions');
            if (actions) actions.classList.add('hidden');
        });

        // 点击选择简历
        const contentArea = resumeItem.querySelector('[data-resume-content]');
        contentArea.addEventListener('click', async (e) => {
            e.stopPropagation();
            await this.selectResume(resumeItem, resume, index);
        });

        // 编辑按钮
        const editBtn = resumeItem.querySelector('.edit-resume-btn');
        editBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.editResume(resume.id);
        });

        // 删除按钮
        const deleteBtn = resumeItem.querySelector('.delete-resume-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showDeleteConfirmDialog(resume.id, resume.version_name || '未命名简历');
        });
    }

    // 选择简历
    async selectResume(resumeItem, resume, index) {
        // 更新视觉状态
        document.querySelectorAll('.version-item').forEach(item => {
            item.classList.remove('bg-primary/5', 'border-primary/20');
            item.classList.add('hover:bg-gray-50');
            const badge = item.querySelector('.text-primary.bg-primary\\/10');
            if (badge) badge.remove();
        });

        resumeItem.classList.remove('hover:bg-gray-50');
        resumeItem.classList.add('bg-primary/5', 'border-primary/20');
        
        const contentArea = resumeItem.querySelector('[data-resume-content]');
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
    }

    // 获取简历详情
    async loadResumeDetail(resumeId) {
        const contentEl = document.getElementById('resumePreviewContent');
        const loadingEl = document.getElementById('resumePreviewLoading');
        const emptyEl = document.getElementById('resumePreviewEmpty');
        const errorEl = document.getElementById('resumePreviewError');

        try {
            console.log('设置当前简历ID:', resumeId);
            this.currentResumeId = resumeId;
            
            // 更新调试信息
            setTimeout(() => this.updateDebugInfo(), 100);
            
            // 显示加载状态
            if (contentEl) contentEl.classList.add('hidden');
            if (emptyEl) emptyEl.classList.add('hidden');
            if (errorEl) errorEl.classList.add('hidden');
            if (loadingEl) loadingEl.classList.remove('hidden');

            const response = await this.callAPI(`/detail/${resumeId}`);
            
            if (response.success && response.data) {
                this.renderResumePreview(response.data);
                console.log('简历详情加载成功，currentResumeId:', this.currentResumeId);
                
                // 延迟加载分析结果
                setTimeout(() => {
                    this.loadResumeAnalysis(resumeId);
                }, 500);
                
                return response.data;
            } else {
                throw new Error('获取简历详情失败');
            }
        } catch (error) {
            console.error('加载简历详情失败:', error);
            this.showResumePreviewError();
            return null;
        } finally {
            if (loadingEl) loadingEl.classList.add('hidden');
        }
    }

    // 渲染简历预览
    renderResumePreview(resumeData) {
        const contentEl = document.getElementById('resumePreviewContent');
        if (!contentEl) return;

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

        contentEl.innerHTML = resumeHTML;
        contentEl.classList.remove('hidden');
    }

    // ==================== AI分析相关函数 ====================

    // 加载简历的AI分析结果
    async loadResumeAnalysis(resumeId) {
        try {
            const response = await this.callAPI(`/analysis/result/${resumeId}`);
            
            if (response.success && response.data) {
                console.log('加载分析结果成功:', response.data);
                this.renderAnalysisResults(response.data);
                return response.data;
            } else {
                console.log('暂无分析结果，显示默认数据');
                return null;
            }
        } catch (error) {
            console.error('加载分析结果失败:', error);
            this.showAnalysisError();
            return null;
        }
    }

    // 触发新的AI分析
    async triggerResumeAnalysis(resumeId, jdContent = '') {
        try {
            console.log('准备触发AI分析:', { resumeId, jdContent: jdContent.substring(0, 100) + '...' });
            
            const requestData = {
                jd_content: jdContent
            };

            console.log('发送API请求:', `/analyze/${resumeId}`, requestData);
            const response = await this.callAPI(`/analyze/${resumeId}`, 'POST', requestData);
            console.log('API响应:', response);
            
            if (response.success) {
                this.currentAnalysisId = response.analysis_id;
                console.log('分析任务已启动:', this.currentAnalysisId);
                
                // 更新调试信息
                this.updateDebugInfo();
                
                // 开始轮询分析状态
                this.startAnalysisPolling();
                
                // 显示分析进行中的UI
                this.showAnalysisInProgress();
                
                // 显示成功消息
                this.showSuccessMessage('AI分析已开始，请稍候...');
                
                return response.analysis_id;
            } else {
                throw new Error(response.message || '启动分析失败');
            }
        } catch (error) {
            console.error('触发分析失败:', error);
            this.showErrorMessage('启动AI分析失败: ' + (error.message || error.toString()));
            return null;
        }
    }

    // 轮询分析状态
    startAnalysisPolling() {
        if (this.analysisPollingInterval) {
            clearInterval(this.analysisPollingInterval);
        }

        this.analysisPollingInterval = setInterval(async () => {
            if (!this.currentAnalysisId) {
                clearInterval(this.analysisPollingInterval);
                return;
            }

            try {
                const response = await this.callAPI(`/analysis/status/${this.currentAnalysisId}`);
                
                if (response.success && response.data) {
                    const analysisData = response.data;
                    this.updateAnalysisProgress(analysisData);

                    if (analysisData.status === 'completed') {
                        clearInterval(this.analysisPollingInterval);
                        this.renderAnalysisResults(analysisData);
                        this.currentAnalysisId = null;
                        this.analysisPollingInterval = null;
                        console.log('AI分析完成');
                        
                        // 更新调试信息
                        this.updateDebugInfo();
                        
                        // 显示完成消息
                        this.showSuccessMessage('AI分析已完成！');
                    } else if (analysisData.status === 'failed') {
                        clearInterval(this.analysisPollingInterval);
                        this.showAnalysisError(analysisData.error || '分析失败');
                        this.currentAnalysisId = null;
                        this.analysisPollingInterval = null;
                        
                        // 更新调试信息
                        this.updateDebugInfo();
                    }
                }
            } catch (error) {
                console.error('获取分析状态失败:', error);
            }
        }, 2000);
    }

    // 手动触发JD分析
    startJDAnalysis() {
        console.log('startJDAnalysis 被调用');
        console.log('当前简历ID:', this.currentResumeId);
        
        const jdTextarea = document.querySelector('textarea');
        const jdContent = jdTextarea ? jdTextarea.value.trim() : '';
        console.log('JD内容:', jdContent);
        
        if (this.currentResumeId) {
            console.log('开始触发分析...');
            this.triggerResumeAnalysis(this.currentResumeId, jdContent);
        } else {
            console.error('没有选中的简历');
            this.showErrorMessage('请先选择一个简历版本');
        }
    }

    // 显示分析进行中的UI
    showAnalysisInProgress() {
        const jdAnalysis = document.querySelector('.jd-analysis-result');
        if (jdAnalysis) {
            jdAnalysis.innerHTML = `
                <div class="analysis-loading text-center py-8">
                    <div class="flex flex-col items-center space-y-4">
                        <div class="w-12 h-12 relative">
                            <div class="w-full h-full border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
                        </div>
                        <div class="space-y-2">
                            <p class="text-sm font-medium text-gray-900" id="analysisStatusText">AI分析进行中...</p>
                            <div class="w-64 bg-gray-200 rounded-full h-2">
                                <div class="bg-primary h-2 rounded-full transition-all duration-500" style="width: 0%" id="overallProgress"></div>
                            </div>
                        </div>
                        <div class="space-y-3 w-full max-w-sm">
                            <div class="flex items-center space-x-3">
                                <div class="w-4 h-4 border-2 border-blue-200 border-t-blue-500 rounded-full animate-spin analysis-step"></div>
                                <span class="text-sm text-gray-600">JD智能匹配分析</span>
                                <div class="flex-1 bg-gray-200 rounded-full h-1">
                                    <div class="bg-blue-500 h-1 rounded-full transition-all duration-500" style="width: 0%" id="jdAnalysisProgress"></div>
                                </div>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="w-4 h-4 border-2 border-gray-300 rounded-full analysis-step"></div>
                                <span class="text-sm text-gray-600">STAR原则检测</span>
                                <div class="flex-1 bg-gray-200 rounded-full h-1">
                                    <div class="bg-yellow-500 h-1 rounded-full transition-all duration-500" style="width: 0%" id="starAnalysisProgress"></div>
                                </div>
                            </div>
                            <div class="flex items-center space-x-3">
                                <div class="w-4 h-4 border-2 border-gray-300 rounded-full analysis-step"></div>
                                <span class="text-sm text-gray-600">简历健康度扫描</span>
                                <div class="flex-1 bg-gray-200 rounded-full h-1">
                                    <div class="bg-green-500 h-1 rounded-full transition-all duration-500" style="width: 0%" id="healthAnalysisProgress"></div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
    }

    // 其他必要的方法...
    showResumeListEmpty() {
        const elements = ['resumeListLoading', 'resumeListEmpty', 'resumeListError'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        const emptyEl = document.getElementById('resumeListEmpty');
        if (emptyEl) emptyEl.classList.remove('hidden');
    }

    showResumeListError() {
        const elements = ['resumeListLoading', 'resumeListEmpty', 'resumeListError'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        const errorEl = document.getElementById('resumeListError');
        if (errorEl) errorEl.classList.remove('hidden');
    }

    showResumePreviewEmpty() {
        const elements = ['resumePreviewContent', 'resumePreviewLoading', 'resumePreviewEmpty', 'resumePreviewError'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        const emptyEl = document.getElementById('resumePreviewEmpty');
        if (emptyEl) emptyEl.classList.remove('hidden');
    }

    showResumePreviewError() {
        const elements = ['resumePreviewContent', 'resumePreviewLoading', 'resumePreviewEmpty', 'resumePreviewError'];
        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.classList.add('hidden');
        });
        const errorEl = document.getElementById('resumePreviewError');
        if (errorEl) errorEl.classList.remove('hidden');
    }

    // 工具函数
    formatDate(dateString) {
        if (!dateString) return '';
        try {
            const date = new Date(dateString);
            return date.toLocaleDateString('zh-CN');
        } catch (error) {
            return dateString;
        }
    }

    // 编辑简历
    editResume(resumeId) {
        if (!resumeId) {
            this.showErrorMessage('简历ID无效');
            return;
        }
        window.location.href = `./Resume_create.html?id=${resumeId}&action=edit`;
    }

    // 显示删除确认对话框
    showDeleteConfirmDialog(resumeId, resumeName) {
        const dialog = document.getElementById('deleteConfirmDialog');
        const nameDisplay = document.getElementById('deleteResumeNameDisplay');
        
        if (dialog && nameDisplay) {
            nameDisplay.textContent = `"${resumeName}"`;
            dialog.classList.remove('hidden');
            
            // 设置当前要删除的简历ID
            dialog.dataset.deleteResumeId = resumeId;
        }
    }

    // 删除简历
    async deleteResume(resumeId) {
        try {
            const response = await this.callAPI(`/delete/${resumeId}`, 'DELETE');
            
            if (response.success) {
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
        }
    }

    // 绑定事件
    bindEvents() {
        // 删除确认对话框事件
        const closeDeleteDialog = document.getElementById('closeDeleteDialog');
        const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
        const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
        const deleteConfirmDialog = document.getElementById('deleteConfirmDialog');

        if (closeDeleteDialog) {
            closeDeleteDialog.addEventListener('click', () => this.hideDeleteConfirmDialog());
        }
        
        if (cancelDeleteBtn) {
            cancelDeleteBtn.addEventListener('click', () => this.hideDeleteConfirmDialog());
        }
        
        if (confirmDeleteBtn) {
            confirmDeleteBtn.addEventListener('click', () => {
                const dialog = document.getElementById('deleteConfirmDialog');
                const resumeId = dialog?.dataset.deleteResumeId;
                if (resumeId) {
                    this.deleteResume(resumeId);
                    this.hideDeleteConfirmDialog();
                }
            });
        }
        
        if (deleteConfirmDialog) {
            deleteConfirmDialog.addEventListener('click', (e) => {
                if (e.target === deleteConfirmDialog) {
                    this.hideDeleteConfirmDialog();
                }
            });
        }

        // 重试按钮
        const retryLoadResumesBtn = document.getElementById('retryLoadResumes');
        if (retryLoadResumesBtn) {
            retryLoadResumesBtn.addEventListener('click', () => this.loadResumesList());
        }

        const retryLoadDetailBtn = document.getElementById('retryLoadResumeDetail');
        if (retryLoadDetailBtn) {
            retryLoadDetailBtn.addEventListener('click', () => {
                if (this.currentResumeId) {
                    this.loadResumeDetail(this.currentResumeId);
                }
            });
        }
    }

    // 隐藏删除确认对话框
    hideDeleteConfirmDialog() {
        const dialog = document.getElementById('deleteConfirmDialog');
        if (dialog) {
            dialog.classList.add('hidden');
            delete dialog.dataset.deleteResumeId;
        }
    }

    // 更新调试信息显示
    updateDebugInfo() {
        const debugInfo = document.getElementById('analysisDebugInfo');
        const debugCurrentResumeId = document.getElementById('debugCurrentResumeId');
        const debugAnalysisStatus = document.getElementById('debugAnalysisStatus');
        
        if (debugInfo && debugCurrentResumeId && debugAnalysisStatus) {
            debugInfo.style.display = 'block';
            debugCurrentResumeId.textContent = this.currentResumeId || '未选择';
            
            if (this.currentAnalysisId && this.analysisPollingInterval) {
                debugAnalysisStatus.textContent = '分析中...';
                debugAnalysisStatus.className = 'text-yellow-600';
            } else if (this.currentResumeId) {
                debugAnalysisStatus.textContent = '准备就绪';
                debugAnalysisStatus.className = 'text-green-600';
            } else {
                debugAnalysisStatus.textContent = '未启动';
                debugAnalysisStatus.className = 'text-gray-500';
            }
        }
    }

    // 确保消息函数存在
    ensureMessageFunctions() {
        if (typeof window.showSuccessMessage === 'undefined') {
            window.showSuccessMessage = (message) => this.showSuccessMessage(message);
        }
        
        if (typeof window.showErrorMessage === 'undefined') {
            window.showErrorMessage = (message) => this.showErrorMessage(message);
        }
    }

    // 显示成功消息
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

    // 显示错误消息
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

    // 显示分析错误
    showAnalysisError(error = '分析加载失败') {
        const jdResult = document.querySelector('.jd-analysis-result');
        if (jdResult) {
            jdResult.innerHTML = `
                <div class="text-center py-8">
                    <div class="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                        <i class="ri-error-warning-line text-red-500 text-xl"></i>
                    </div>
                    <p class="text-red-600 mb-4">${error}</p>
                    <button onclick="resumeManager.startJDAnalysis()" class="px-4 py-2 bg-primary text-white rounded-button hover:bg-primary/90 transition-colors">
                        重新分析
                    </button>
                </div>
            `;
        }
    }

    // 调试功能
    debug() {
        console.log('=== 简历分析调试信息 ===');
        console.log('currentResumeId:', this.currentResumeId);
        console.log('currentAnalysisId:', this.currentAnalysisId);
        console.log('分析轮询状态:', this.analysisPollingInterval ? '进行中' : '未启动');
        console.log('简历列表:', this.resumesList);
        
        const jdTextarea = document.querySelector('textarea');
        console.log('JD输入框:', jdTextarea);
        console.log('JD内容:', jdTextarea ? jdTextarea.value : '未找到');
        
        console.log('========================');
        this.updateDebugInfo();
    }

    // 简化的分析相关方法（其他复杂的分析渲染方法可以按需添加）
    renderAnalysisResults(analysisData) {
        console.log('渲染分析结果:', analysisData);
        // 这里可以添加具体的渲染逻辑
    }

    updateAnalysisProgress(analysisData) {
        const progress = analysisData.progress || 0;
        const status = analysisData.status;
        
        // 更新进度条和状态文本
        const progressBar = document.getElementById('overallProgress');
        if (progressBar) {
            progressBar.style.width = progress + '%';
        }
        
        const statusText = document.getElementById('analysisStatusText');
        if (statusText) {
            const statusMessages = {
                'processing': '准备中...',
                'analyzing_jd': 'JD智能匹配分析中...',
                'analyzing_star': 'STAR原则检测中...',
                'analyzing_health': '简历健康度扫描中...'
            };
            statusText.textContent = statusMessages[status] || `分析中... ${progress}%`;
        }
    }
}

// 全局变量和函数
let resumeManager;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    resumeManager = new ResumeManagement();
});

// 全局函数（供HTML调用）
window.startJDAnalysis = function() {
    if (resumeManager) {
        resumeManager.startJDAnalysis();
    }
};

window.debugResumeAnalysis = function() {
    if (resumeManager) {
        resumeManager.debug();
    }
};

window.retryAnalysis = function() {
    if (resumeManager && resumeManager.currentResumeId) {
        resumeManager.triggerResumeAnalysis(resumeManager.currentResumeId);
    }
};
