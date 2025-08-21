/**
 * 视频分析管理器
 * 处理实时视频捕获、分析和结果显示
 * 集成多模态分析接口
 */

class VideoAnalysisManager {
    constructor() {
        this.websocket = null;
        this.isConnected = false;
        this.isAnalyzing = false;
        this.sessionId = null;
        this.userId = null;
        
        // 视频相关
        this.videoElement = null;
        this.canvas = null;
        this.context = null;
        this.captureInterval = null;
        this.frameRate = 2; // 每秒捕获2帧
        
        // 分析结果缓存
        this.analysisHistory = [];
        this.currentAnalysis = null;
        
        // 体态语言分析器
        this.bodyLanguageAnalyzer = null;
        
        // UI元素引用
        this.analysisPanel = {
            microExpressions: {
                confidence: document.querySelector('[data-analysis="confidence"]'),
                tension: document.querySelector('[data-analysis="tension"]'), 
                focus: document.querySelector('[data-analysis="focus"]')
            },
            bodyLanguage: {
                eyeContact: document.querySelector('[data-analysis="eye-contact"]'),
                headStability: document.querySelector('[data-analysis="head-stability"]'),
                posture: document.querySelector('[data-analysis="posture"]')
            },
            qualityAssessment: {
                logic: document.querySelector('[data-analysis="logic"]'),
                completeness: document.querySelector('[data-analysis="completeness"]'),
                relevance: document.querySelector('[data-analysis="relevance"]')
            },
            suggestions: document.querySelector('[data-analysis="suggestions"]')
        };
        
        console.log('📹 视频分析管理器初始化完成');
    }
    
    /**
     * 初始化视频分析
     */
    async initialize(userId, videoElement) {
        try {
            this.userId = userId;
            this.videoElement = videoElement;
            
            console.log('🎬 开始视频分析管理器初始化');
            console.log('👤 用户ID:', userId);
            console.log('🎥 视频元素:', videoElement.id || videoElement);
            
            // 创建离屏canvas用于帧捕获
            this.canvas = document.createElement('canvas');
            this.context = this.canvas.getContext('2d');
            
            // 等待视频准备就绪
            const isReady = await this.waitForVideoReady();
            if (!isReady) {
                console.error('❌ 视频元素准备失败');
                return false;
            }
            
            // 初始化体态语言分析器
            if (window.BodyLanguageAnalyzer) {
                this.bodyLanguageAnalyzer = new window.BodyLanguageAnalyzer();
                console.log('🧍 体态语言分析器已集成');
            } else {
                console.warn('⚠️ BodyLanguageAnalyzer未加载，体态语言分析功能不可用');
            }
            
            console.log('✅ 视频分析管理器初始化成功');
            return true;
        } catch (error) {
            console.error('❌ 视频分析管理器初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 等待视频元素准备就绪
     * @returns {Promise<boolean>} - 是否准备就绪
     */
    async waitForVideoReady() {
        return new Promise((resolve) => {
            const maxWaitTime = 10000; // 最多等待10秒
            const checkInterval = 100; // 每100ms检查一次
            let elapsedTime = 0;
            
            const checkReady = () => {
                console.log('🔍 检查视频状态:', {
                    srcObject: !!this.videoElement.srcObject,
                    videoWidth: this.videoElement.videoWidth,
                    videoHeight: this.videoElement.videoHeight,
                    readyState: this.videoElement.readyState,
                    currentTime: this.videoElement.currentTime,
                    paused: this.videoElement.paused
                });
                
                // 检查视频是否有媒体流且有尺寸
                if (this.videoElement.srcObject && 
                    this.videoElement.videoWidth > 0 && 
                    this.videoElement.videoHeight > 0 &&
                    this.videoElement.readyState >= 2) { // HAVE_CURRENT_DATA
                    
                    console.log('✅ 视频已准备就绪:', {
                        size: `${this.videoElement.videoWidth}x${this.videoElement.videoHeight}`,
                        readyState: this.videoElement.readyState
                    });
                    resolve(true);
                    return;
                }
                
                elapsedTime += checkInterval;
                
                if (elapsedTime >= maxWaitTime) {
                    console.error('❌ 视频准备超时');
                    resolve(false);
                    return;
                }
                
                // 如果没有媒体流，显示相应提示
                if (!this.videoElement.srcObject) {
                    console.warn('⚠️ 等待摄像头媒体流...');
                } else if (this.videoElement.videoWidth === 0 || this.videoElement.videoHeight === 0) {
                    console.warn('⚠️ 等待视频尺寸信息...');
                } else if (this.videoElement.readyState < 2) {
                    console.warn('⚠️ 等待视频数据加载...');
                }
                
                setTimeout(checkReady, checkInterval);
            };
            
            checkReady();
        });
    }
    
    /**
     * 创建视频分析会话
     */
    async createSession(userId) {
        try {
            const response = await fetch('/api/v1/video/create-video-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    user_id: userId
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP错误: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                this.sessionId = data.session_id;
                console.log('✅ 视频分析会话创建成功:', this.sessionId);
                console.log('🔬 DeepFace可用性:', data.deepface_available);
                
                // 显示DeepFace状态提示
                if (!data.deepface_available) {
                    this.showNotification('⚠️ DeepFace不可用，情绪分析功能受限', 'warning');
                }
                
                return data.session_id;
            } else {
                throw new Error(data.message || '创建会话失败');
            }
        } catch (error) {
            console.error('❌ 创建视频分析会话失败:', error);
            this.showNotification('创建视频分析会话失败: ' + error.message, 'error');
            return null;
        }
    }
    
    /**
     * 连接到视频分析WebSocket
     */
    async connectWebSocket(sessionId) {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/v1/video/video-analysis/${sessionId}`;
            
            console.log('🔗 连接视频分析WebSocket:', wsUrl);
            
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = () => {
                this.isConnected = true;
                console.log('✅ 视频分析WebSocket连接成功');
                this.showNotification('视频分析连接已建立', 'success');
            };
            
            this.websocket.onmessage = (event) => {
                this.handleWebSocketMessage(JSON.parse(event.data));
            };
            
            this.websocket.onclose = () => {
                this.isConnected = false;
                this.isAnalyzing = false;
                console.log('🔌 视频分析WebSocket连接已关闭');
                this.showNotification('视频分析连接已断开', 'info');
            };
            
            this.websocket.onerror = (error) => {
                console.error('❌ 视频分析WebSocket错误:', error);
                this.showNotification('视频分析连接错误', 'error');
            };
            
            return new Promise((resolve) => {
                const checkConnection = () => {
                    if (this.isConnected) {
                        resolve(true);
                    } else if (this.websocket.readyState === WebSocket.CLOSED) {
                        resolve(false);
                    } else {
                        setTimeout(checkConnection, 100);
                    }
                };
                checkConnection();
            });
        } catch (error) {
            console.error('❌ WebSocket连接失败:', error);
            return false;
        }
    }
    
    /**
     * 处理WebSocket消息
     */
    handleWebSocketMessage(message) {
        console.log('📥 收到视频分析消息:', message.type);
        
        switch (message.type) {
            case 'session_ready':
                console.log('🎬 视频分析会话准备就绪');
                break;
                
            case 'analysis_update':
                this.handleAnalysisUpdate(message);
                break;
                
            case 'status':
                console.log('📊 状态更新:', message.status, message.message);
                break;
                
            case 'error':
                console.error('❌ 视频分析错误:', message.message);
                this.showNotification('分析错误: ' + message.message, 'error');
                break;
                
            default:
                console.log('❓ 未知消息类型:', message.type);
        }
    }
    
    /**
     * 处理分析结果更新
     */
    handleAnalysisUpdate(message) {
        this.currentAnalysis = message;
        this.analysisHistory.push({
            timestamp: message.timestamp,
            analysis: message
        });
        
        // 处理体态语言分析数据
        if (this.bodyLanguageAnalyzer && (message.body_language || message.gestures)) {
            console.log('🔄 视频分析管理器传递数据给体态语言分析器:', {
                body_language: message.body_language,
                gestures: message.gestures
            });
            this.bodyLanguageAnalyzer.processAnalysisData(message);
        } else if (this.bodyLanguageAnalyzer) {
            console.log('⚠️ 收到视频分析数据，但没有体态语言/手势数据');
        } else {
            console.log('⚠️ 体态语言分析器未初始化');
        }
        
        // 更新UI显示
        this.updateAnalysisPanel(message);
        
        // 保持历史记录不超过100条
        if (this.analysisHistory.length > 100) {
            this.analysisHistory.shift();
        }
        
        console.log('📊 分析结果已更新:', {
            emotion: message.micro_expressions?.dominant_emotion,
            confidence: message.micro_expressions?.confidence + '%',
            eyeContact: message.body_language?.eye_contact_ratio + '%'
        });
    }
    
    /**
     * 更新分析面板显示
     */
    updateAnalysisPanel(analysis) {
        try {
            // 更新微表情洞察
            if (analysis.micro_expressions) {
                this.updateMicroExpressions(analysis.micro_expressions);
            }
            
            // 更新体态语言分析
            if (analysis.body_language) {
                this.updateBodyLanguage(analysis.body_language);
            }
            
            // 更新回答质量评估
            if (analysis.quality_assessment) {
                this.updateQualityAssessment(analysis.quality_assessment);
            }
            
            // 更新建议
            if (analysis.suggestions) {
                this.updateSuggestions(analysis.suggestions);
            }
            
        } catch (error) {
            console.error('❌ 更新分析面板失败:', error);
        }
    }
    
    /**
     * 更新微表情显示
     */
    updateMicroExpressions(microExpressions) {
        const { dominant_emotion, confidence, tension, focus } = microExpressions;
        
        // 更新自信度
        const confidenceElement = document.querySelector('.space-y-2 .bg-green-50 .font-semibold');
        if (confidenceElement) {
            confidenceElement.textContent = `${confidence}%`;
        }
        
        // 更新紧张度 
        const tensionElement = document.querySelector('.space-y-2 .bg-yellow-50 .font-semibold');
        if (tensionElement) {
            tensionElement.textContent = `${tension}%`;
        }
        
        // 更新专注度
        const focusElement = document.querySelector('.space-y-2 .bg-blue-50 .font-semibold');
        if (focusElement) {
            focusElement.textContent = `${focus}%`;
        }
        
        // 更新情绪显示
        this.updateEmotionDisplay(dominant_emotion);
    }
    
    /**
     * 更新体态语言显示
     */
    updateBodyLanguage(bodyLanguage) {
        const { eye_contact_ratio, head_stability, posture_score } = bodyLanguage;
        
        // 查找体态语言分析区域并更新
        const bodyLanguageSection = document.querySelector('h3').parentElement;
        if (bodyLanguageSection) {
            const items = bodyLanguageSection.querySelectorAll('.flex.items-start.space-x-2');
            
            // 更新眼神接触
            if (items[0]) {
                const eyeContactText = items[0].querySelector('p:first-of-type');
                const eyeContactDesc = items[0].querySelector('p:last-of-type');
                if (eyeContactText && eyeContactDesc) {
                    eyeContactText.textContent = eye_contact_ratio >= 70 ? '眼神接触良好' : '眼神接触需要改善';
                    eyeContactDesc.textContent = `保持了 ${eye_contact_ratio}% 的时间`;
                    
                    // 更新状态指示点
                    const indicator = items[0].querySelector('.w-2.h-2');
                    if (indicator) {
                        indicator.className = eye_contact_ratio >= 70 ? 
                            'w-2 h-2 bg-green-400 rounded-full mt-2' : 
                            'w-2 h-2 bg-yellow-400 rounded-full mt-2';
                    }
                }
            }
            
            // 更新头部稳定性
            if (items[1]) {
                const stabilityText = items[1].querySelector('p:first-of-type');
                const stabilityDesc = items[1].querySelector('p:last-of-type');
                if (stabilityText && stabilityDesc) {
                    stabilityText.textContent = head_stability >= 70 ? '头部姿态稳定' : '头部略显不稳';
                    stabilityDesc.textContent = head_stability >= 70 ? '保持得很好' : '尝试保持稳定';
                    
                    const indicator = items[1].querySelector('.w-2.h-2');
                    if (indicator) {
                        indicator.className = head_stability >= 70 ? 
                            'w-2 h-2 bg-green-400 rounded-full mt-2' : 
                            'w-2 h-2 bg-yellow-400 rounded-full mt-2';
                    }
                }
            }
            
            // 更新姿态评分
            if (items[2]) {
                const postureText = items[2].querySelector('p:first-of-type');
                const postureDesc = items[2].querySelector('p:last-of-type');
                if (postureText && postureDesc) {
                    postureText.textContent = posture_score >= 80 ? '姿态表现优秀' : '姿态需要调整';
                    postureDesc.textContent = `当前评分: ${posture_score}分`;
                }
            }
        }
    }
    
    /**
     * 更新回答质量评估
     */
    updateQualityAssessment(qualityAssessment) {
        const { logic_score, completeness_score, relevance_score } = qualityAssessment;
        
        // 查找质量评估区域
        const qualitySection = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('回答质量评估'));
        if (qualitySection) {
            const progressBars = qualitySection.parentElement.querySelectorAll('.w-16.h-2.bg-gray-200');
            
            // 更新逻辑性进度条
            if (progressBars[0]) {
                const logicBar = progressBars[0].querySelector('div');
                if (logicBar) {
                    logicBar.style.width = `${(logic_score / 100) * 16 * 4}px`; // 16*0.25rem per unit
                }
                const logicPercent = progressBars[0].parentElement.querySelector('.text-xs');
                if (logicPercent) {
                    logicPercent.textContent = `${logic_score}%`;
                }
            }
            
            // 更新完整性进度条
            if (progressBars[1]) {
                const completenessBar = progressBars[1].querySelector('div');
                if (completenessBar) {
                    completenessBar.style.width = `${(completeness_score / 100) * 16 * 4}px`;
                }
                const completenessPercent = progressBars[1].parentElement.querySelector('.text-xs');
                if (completenessPercent) {
                    completenessPercent.textContent = `${completeness_score}%`;
                }
            }
            
            // 更新相关性进度条
            if (progressBars[2]) {
                const relevanceBar = progressBars[2].querySelector('div');
                if (relevanceBar) {
                    relevanceBar.style.width = `${(relevance_score / 100) * 16 * 4}px`;
                }
                const relevancePercent = progressBars[2].parentElement.querySelector('.text-xs');
                if (relevancePercent) {
                    relevancePercent.textContent = `${relevance_score}%`;
                }
            }
        }
    }
    
    /**
     * 更新建议显示
     */
    updateSuggestions(suggestions) {
        const suggestionsSection = Array.from(document.querySelectorAll('h3')).find(h => h.textContent.includes('即时优化建议'));
        if (suggestionsSection) {
            const suggestionsContainer = suggestionsSection.parentElement.querySelector('.space-y-2');
            if (suggestionsContainer) {
                // 清空现有建议
                suggestionsContainer.innerHTML = '';
                
                // 添加新建议
                suggestions.forEach(suggestion => {
                    const suggestionElement = this.createSuggestionElement(suggestion);
                    suggestionsContainer.appendChild(suggestionElement);
                });
            }
        }
    }
    
    /**
     * 创建建议元素
     */
    createSuggestionElement(suggestion) {
        const div = document.createElement('div');
        
        const colorClass = {
            'success': 'bg-green-50 border-green-100 text-green-700',
            'info': 'bg-blue-50 border-blue-100 text-blue-700',
            'warning': 'bg-yellow-50 border-yellow-100 text-yellow-700',
            'error': 'bg-red-50 border-red-100 text-red-700'
        }[suggestion.type] || 'bg-blue-50 border-blue-100 text-blue-700';
        
        div.className = `p-3 rounded-lg border ${colorClass}`;
        div.innerHTML = `<p class="text-sm">${suggestion.message}</p>`;
        
        return div;
    }
    
    /**
     * 更新情绪显示
     */
    updateEmotionDisplay(emotion) {
        // 可以在这里添加特殊的情绪显示逻辑
        console.log('😊 当前主导情绪:', emotion);
    }
    
    /**
     * 开始视频分析
     */
    async startAnalysis() {
        if (!this.isConnected || !this.videoElement) {
            console.error('❌ 无法开始分析: WebSocket未连接或视频元素不可用');
            this.showNotification('无法开始分析: 连接或视频不可用', 'error');
            return false;
        }
        
        // 检查视频是否正在播放
        if (this.videoElement.videoWidth === 0 || this.videoElement.videoHeight === 0) {
            console.warn('⚠️ 视频尺寸为零，等待视频加载...');
            this.showNotification('等待摄像头加载...', 'info');
            // 等待一下再重试
            setTimeout(() => this.startAnalysis(), 1000);
            return false;
        }
        
        try {
            // 发送开始分析命令
            this.websocket.send(JSON.stringify({
                command: 'start_analysis'
            }));
            
            this.isAnalyzing = true;
            
            // 开始帧捕获
            this.startFrameCapture();
            
            console.log('🎬 视频分析已开始');
            console.log('📊 视频尺寸:', this.videoElement.videoWidth, 'x', this.videoElement.videoHeight);
            this.showNotification('实时视频分析已开启', 'success');
            
            // 启动体态语言分析
            if (this.bodyLanguageAnalyzer) {
                this.bodyLanguageAnalyzer.startAnalysis();
            }
            
            // 更新UI状态
            this.updateAnalysisStatus(true);
            
            return true;
        } catch (error) {
            console.error('❌ 开始分析失败:', error);
            this.showNotification('开始分析失败: ' + error.message, 'error');
            return false;
        }
    }
    
    /**
     * 停止视频分析
     */
    async stopAnalysis() {
        try {
            if (this.captureInterval) {
                clearInterval(this.captureInterval);
                this.captureInterval = null;
            }
            
            if (this.websocket && this.isConnected) {
                this.websocket.send(JSON.stringify({
                    command: 'stop_analysis'
                }));
            }
            
            this.isAnalyzing = false;
            
            // 停止体态语言分析
            if (this.bodyLanguageAnalyzer) {
                this.bodyLanguageAnalyzer.stopAnalysis();
            }
            
            // 更新UI状态
            this.updateAnalysisStatus(false);
            
            console.log('⏹️ 视频分析已停止');
            this.showNotification('视频分析已停止', 'info');
            
        } catch (error) {
            console.error('❌ 停止分析失败:', error);
            this.showNotification('停止分析时出错: ' + error.message, 'error');
        }
    }
    
    /**
     * 开始帧捕获
     */
    startFrameCapture() {
        if (this.captureInterval) {
            clearInterval(this.captureInterval);
        }
        
        this.captureInterval = setInterval(() => {
            this.captureAndSendFrame();
        }, 1000 / this.frameRate); // 每秒frameRate帧
        
        console.log(`📸 开始帧捕获 (${this.frameRate} FPS)`);
    }
    
    /**
     * 捕获并发送视频帧
     */
    captureAndSendFrame() {
        if (!this.videoElement || !this.isAnalyzing || !this.isConnected) {
            console.warn('🚫 帧捕获跳过:', {
                videoElement: !!this.videoElement,
                isAnalyzing: this.isAnalyzing,
                isConnected: this.isConnected
            });
            return;
        }
        
        try {
            // 详细的视频元素状态检查
            const videoStatus = {
                videoWidth: this.videoElement.videoWidth,
                videoHeight: this.videoElement.videoHeight,
                readyState: this.videoElement.readyState,
                currentTime: this.videoElement.currentTime,
                duration: this.videoElement.duration,
                paused: this.videoElement.paused,
                muted: this.videoElement.muted,
                srcObject: !!this.videoElement.srcObject,
                videoTracks: this.videoElement.srcObject ? this.videoElement.srcObject.getVideoTracks().length : 0,
                isVisible: this.videoElement.offsetWidth > 0 && this.videoElement.offsetHeight > 0,
                style: {
                    display: getComputedStyle(this.videoElement).display,
                    visibility: getComputedStyle(this.videoElement).visibility,
                    opacity: getComputedStyle(this.videoElement).opacity
                }
            };
            
            console.log('🎥 视频元素状态:', videoStatus);
            
            // 检查视频是否有有效尺寸
            if (this.videoElement.videoWidth === 0 || this.videoElement.videoHeight === 0) {
                console.warn('⚠️ 视频尺寸为0，等待视频加载完成...');
                this.showNotification('等待视频加载完成...', 'warning');
                return;
            }
            
            // 检查视频是否在播放状态
            if (this.videoElement.readyState < 2) { // HAVE_CURRENT_DATA
                console.warn('⚠️ 视频数据未就绪，readyState:', this.videoElement.readyState);
                this.showNotification('视频数据加载中...', 'info');
                return;
            }
            
            // 设置canvas尺寸
            this.canvas.width = this.videoElement.videoWidth;
            this.canvas.height = this.videoElement.videoHeight;
            
            console.log('🖼️ Canvas尺寸设置:', this.canvas.width, 'x', this.canvas.height);
            
            // 清空canvas（用于检测是否有内容）
            this.context.fillStyle = '#FF0000'; // 红色背景用于调试
            this.context.fillRect(0, 0, this.canvas.width, this.canvas.height);
            
            // 绘制当前视频帧到canvas
            this.context.drawImage(this.videoElement, 0, 0, this.canvas.width, this.canvas.height);
            
            // 检查canvas内容是否有变化
            const imageData = this.context.getImageData(0, 0, this.canvas.width, this.canvas.height);
            const data = imageData.data;
            let hasNonRedPixels = false;
            
            // 检查前100个像素是否有非红色内容
            for (let i = 0; i < Math.min(data.length, 400); i += 4) {
                if (data[i] !== 255 || data[i + 1] !== 0 || data[i + 2] !== 0) {
                    hasNonRedPixels = true;
                    break;
                }
            }
            
            if (!hasNonRedPixels) {
                console.error('❌ Canvas内容似乎没有变化（仍为红色背景），视频可能没有绘制成功');
                this.showNotification('视频画面捕获失败', 'error');
            } else {
                console.log('✅ Canvas已成功绘制视频内容');
            }
            
            // 转换为Blob然后发送二进制数据
            this.canvas.toBlob((blob) => {
                if (!blob) {
                    console.error('❌ Canvas转换为Blob失败');
                    return;
                }
                
                console.log('📦 Blob创建成功:', {
                    size: blob.size,
                    type: blob.type
                });
                
                if (blob.size < 1000) {
                    console.warn('⚠️ Blob尺寸异常小 (<1000 bytes)，可能是全黑图像');
                }
                
                if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                    // 将Blob转换为ArrayBuffer并发送
                    blob.arrayBuffer().then(arrayBuffer => {
                        this.websocket.send(arrayBuffer);
                        console.log('📸 发送视频帧:', {
                            bytes: arrayBuffer.byteLength,
                            timestamp: new Date().toISOString()
                        });
                    }).catch(error => {
                        console.error('❌ 转换ArrayBuffer失败:', error);
                    });
                } else {
                    console.error('❌ WebSocket未连接，无法发送帧');
                }
            }, 'image/jpeg', 0.8);
            
        } catch (error) {
            console.error('❌ 帧捕获失败:', error);
            console.error('🔧 错误详情:', error.stack);
        }
    }
    
    /**
     * 关闭连接
     */
    async close() {
        try {
            await this.stopAnalysis();
            
            if (this.websocket) {
                this.websocket.close();
                this.websocket = null;
            }
            
            this.isConnected = false;
            this.sessionId = null;
            
            // 清理体态语言分析器
            if (this.bodyLanguageAnalyzer) {
                this.bodyLanguageAnalyzer.destroy();
                this.bodyLanguageAnalyzer = null;
            }
            
            console.log('🔚 视频分析管理器已关闭');
            
        } catch (error) {
            console.error('❌ 关闭视频分析管理器失败:', error);
        }
    }
    
    /**
     * 获取分析历史
     */
    getAnalysisHistory() {
        return this.analysisHistory;
    }
    
    /**
     * 获取当前分析结果
     */
    getCurrentAnalysis() {
        return this.currentAnalysis;
    }
    
    /**
     * 显示通知
     */
    showNotification(message, type = 'info') {
        // 这里可以集成现有的通知系统
        console.log(`📢 [${type.toUpperCase()}] ${message}`);
        
        // 如果有全局通知函数，调用它
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        }
        
        // 简单的页面通知显示（可以用更好的UI组件替换）
        this.showPageNotification(message, type);
    }
    
    /**
     * 显示页面通知
     */
    showPageNotification(message, type) {
        // 创建通知元素
        const notification = document.createElement('div');
        notification.className = `fixed top-20 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm transition-all duration-300`;
        
        // 根据类型设置样式
        const styles = {
            'success': 'bg-green-100 border-green-500 text-green-800',
            'error': 'bg-red-100 border-red-500 text-red-800',
            'warning': 'bg-yellow-100 border-yellow-500 text-yellow-800',
            'info': 'bg-blue-100 border-blue-500 text-blue-800'
        };
        
        notification.className += ` ${styles[type] || styles.info} border-l-4`;
        notification.textContent = message;
        
        // 添加到页面
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 3000);
    }
    
    /**
     * 更新分析状态显示
     */
    updateAnalysisStatus(isAnalyzing) {
        // 更新底部状态指示器
        const statusElements = document.querySelectorAll('[data-status="analysis"]');
        statusElements.forEach(element => {
            if (isAnalyzing) {
                element.textContent = 'AI 视频分析中';
                element.className = element.className.replace('bg-gray-500', 'bg-green-500');
            } else {
                element.textContent = 'AI 分析已停止';
                element.className = element.className.replace('bg-green-500', 'bg-gray-500');
            }
        });
        
        // 更新分析面板状态
        const analysisPanel = document.getElementById('analysisPanel');
        if (analysisPanel) {
            const statusIndicator = analysisPanel.querySelector('[data-analysis-status]');
            if (statusIndicator) {
                statusIndicator.textContent = isAnalyzing ? '实时分析中...' : '分析已停止';
                statusIndicator.className = isAnalyzing ? 
                    'text-green-600 text-sm' : 'text-gray-500 text-sm';
            }
        }
    }
    
    /**
     * 重置分析数据
     */
    resetAnalysis() {
        this.analysisHistory = [];
        this.currentAnalysis = null;
        
        if (this.websocket && this.isConnected) {
            this.websocket.send(JSON.stringify({
                command: 'reset_analysis'
            }));
        }
        
        console.log('🔄 分析数据已重置');
    }
}

// 全局实例
window.VideoAnalysisManager = VideoAnalysisManager;

// 导出供其他模块使用
if (typeof module !== 'undefined' && module.exports) {
    module.exports = VideoAnalysisManager;
}
