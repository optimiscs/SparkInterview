/**
 * 简化语音模块 - 统一语音识别和聊天集成
 * 合并了原有的三个语音JS文件的功能，简化停止方式
 * 
 * 完整音频录制配置：
 * - 录制所有音频数据，包含噪音、静音和背景声音
 * - 禁用浏览器音频处理（回声消除、噪声抑制等）
 * - 确保不丢失任何语音内容，包括轻声、模糊音等
 * - 40ms间隔连续发送音频片段
 * 
 * 调试命令：
 * simplifiedVoiceModule.enableDebugMode(true)    // 启用调试模式
 * simplifiedVoiceModule.setRecordAllAudio(true)  // 启用完整录音
 * simplifiedVoiceModule.getConfig()              // 查看当前配置
 */

class SimplifiedVoiceModule {
    constructor() {
        this.websocket = null;
        this.mediaRecorder = null;
        this.audioStream = null;
        this.isRecording = false;
        this.recognizedText = '';
        this.accumulatedText = '';
        
        // DOM元素
        this.voiceToggle = document.getElementById('voiceToggle');
        this.voiceIndicator = document.getElementById('voiceIndicator');
        this.messageInput = document.getElementById('messageInput');
        this.sendButton = document.getElementById('sendButton');
        this.messagesContainer = document.getElementById('chat-messages-container');
        
        // 状态
        this.currentMessageId = null;
        this.backendSessionId = null;
        this.waitingForFinal = false;
        this.finalResultTimeout = null;
        this.lastRecognizedText = '';  // 保存最后一次识别的文本
        
        // 音频配置
        this.recordAllAudio = true;  // 录制所有音频，包含噪音和静音
        this.debugMode = false;  // 调试模式
        
        this.init();
    }
    
    init() {
        if (!this.voiceToggle) {
            console.warn('⚠️ 未找到语音按钮');
            return;
        }
        
        this.bindEvents();
        this.addVoicePreview();
        console.log('🎤 简化语音模块初始化完成');
    }
    
    bindEvents() {
        // 语音按钮点击事件 - 唯一的启停方式
        this.voiceToggle.addEventListener('click', () => {
            if (this.isRecording) {
                this.stopRecording();
            } else {
                this.startRecording();
            }
        });
        
        // ESC键停止录音
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isRecording) {
                this.stopRecording();
            }
        });
    }
    
    addVoicePreview() {
        // 添加语音预览窗口
        const previewHTML = `
            <div id="voice-preview" class="fixed bottom-32 left-1/2 transform -translate-x-1/2 bg-white border border-gray-200 rounded-lg shadow-lg p-4 z-50 max-w-md hidden">
                <div class="flex items-center justify-between mb-2">
                    <span class="text-sm font-medium text-gray-900">语音识别</span>
                    <div class="flex items-center space-x-2">
                        <div class="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                        <span class="text-xs text-gray-500">录音中</span>
                    </div>
                </div>
                <div id="voice-text" class="text-sm text-gray-900 min-h-[40px] max-h-32 overflow-y-auto bg-gray-50 p-2 rounded">
                    等待语音输入...
                </div>
                <div class="flex items-center justify-between mt-2">
                    <span class="text-xs text-gray-500">说"回答结束"或点击停止</span>
                    <button id="voice-stop-btn" class="text-xs text-red-600 hover:text-red-800">
                        <i class="ri-stop-circle-line mr-1"></i>停止
                    </button>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', previewHTML);
        
        // 绑定停止按钮
        document.getElementById('voice-stop-btn')?.addEventListener('click', () => {
            this.stopRecording();
        });
    }
    
    async startRecording() {
        if (this.isRecording) return;
        
        try {
            console.log('🎤 开始语音识别...');
            
            // 1. 获取麦克风权限
            await this.requestMicrophone();
            
            // 2. 创建后端会话
            await this.createSession();
            
            // 3. 连接WebSocket
            await this.connectWebSocket();
            
            // 4. 更新UI
            this.updateUI(true);
            this.showPreview(true);
            this.createVoiceMessage();
            
            this.isRecording = true;
            console.log('✅ 语音识别已启动');
            
        } catch (error) {
            console.error('❌ 启动失败:', error);
            this.showError(`启动失败: ${error.message}`);
            this.cleanup();
        }
    }
    
    async stopRecording() {
        if (!this.isRecording) return;
        
        try {
            console.log('⏹️ 停止语音识别...');
            this.isRecording = false;
            
            // 发送停止命令
            if (this.websocket?.readyState === WebSocket.OPEN) {
                this.websocket.send(JSON.stringify({ command: 'stop' }));
            }
            
            // 立即更新UI状态，但不隐藏预览窗口
            this.updateUI(false);
            
            // 等待最终结果，设置超时机制
            this.waitingForFinal = true;
            
            // 立即更新消息状态为"处理中"
            this.updateVoiceMessage(this.lastRecognizedText || this.recognizedText, false);
            
            // 更新预览窗口文本
            this.updateVoiceText((this.lastRecognizedText || this.recognizedText) + ' (处理中...)');
            
            this.finalResultTimeout = setTimeout(() => {
                console.log('⏰ 等待最终结果超时，使用当前文本');
                this.handleTimeoutFinal();
            }, 2000); // 等待2秒获取最终结果
            
            console.log('✅ 语音识别停止中，等待最终结果...');
            
        } catch (error) {
            console.error('❌ 停止失败:', error);
            this.cleanup();
        }
    }
    
    async requestMicrophone() {
        this.audioStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: false,      // 禁用回声消除，保留完整音频
                noiseSuppression: false,      // 禁用噪声抑制，包含所有声音
                autoGainControl: false,       // 禁用自动增益控制
                latency: 0.01,               // 降低延迟
                volume: 1.0                  // 最大音量
            }
        });
        
        console.log('🎤 音频流配置: 完整录音模式，包含噪音和静音');
    }
    
    async createSession() {
        const userId = this.getStableUserId();
        const interviewId = this.getStableInterviewId();
        
        const response = await fetch('http://localhost:8000/api/v1/voice/create-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_id: userId,
                interview_session_id: interviewId
            })
        });
        
        const result = await response.json();
        if (result.success) {
            this.backendSessionId = result.session_id;
            console.log('✅ 会话创建成功:', this.backendSessionId);
        } else {
            throw new Error(result.detail || '创建会话失败');
        }
    }
    
    getStableUserId() {
        let userId = sessionStorage.getItem('voice_user_id');
        if (!userId) {
            userId = 'user_' + Math.random().toString(36).substr(2, 9);
            sessionStorage.setItem('voice_user_id', userId);
        }
        return userId;
    }
    
    getStableInterviewId() {
        let interviewId = sessionStorage.getItem('voice_interview_id');
        if (!interviewId) {
            interviewId = 'interview_' + Date.now();
            sessionStorage.setItem('voice_interview_id', interviewId);
        }
        return interviewId;
    }
    
    async connectWebSocket() {
        return new Promise((resolve, reject) => {
            const wsUrl = `ws://localhost:8000/api/v1/voice/recognition/${this.backendSessionId}`;
            this.websocket = new WebSocket(wsUrl);
            
            this.websocket.onopen = async () => {
                console.log('✅ WebSocket连接成功');
                // 连接成功后立即开始音频捕获
                await this.startAudioCapture();
                resolve();
            };
            
            this.websocket.onmessage = (event) => {
                this.handleMessage(event.data);
            };
            
            this.websocket.onerror = () => {
                reject(new Error('WebSocket连接失败'));
            };
            
            this.websocket.onclose = () => {
                console.log('🔌 WebSocket连接关闭');
                this.cleanup();
            };
        });
    }
    
    async startAudioCapture() {
        try {
            // 创建音频上下文
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000
            });
            
            // 创建音频源
            const source = this.audioContext.createMediaStreamSource(this.audioStream);
            
            // 音频分片配置：每40ms发送640样本(1280字节) - 完整录音模式
            this.chunkDuration = 40; // ms
            this.chunkSamples = Math.floor(16000 * this.chunkDuration / 1000); // 640 samples
            this.chunkBytes = this.chunkSamples * 2; // 1280 bytes (16-bit samples)
            this.audioBuffer = new Float32Array(0);
            
            console.log(`🎵 音频配置: ${this.chunkDuration}ms间隔, ${this.chunkSamples}样本, ${this.chunkBytes}字节 [完整录音模式]`);
            
            // 创建处理器节点 (使用1024样本缓冲区，然后进行分片)
            this.processor = this.audioContext.createScriptProcessor(1024, 1, 1);
            
            // 处理音频数据 - 完整录音模式
            this.processor.onaudioprocess = (event) => {
                if (this.isRecording && this.websocket?.readyState === WebSocket.OPEN) {
                    const inputBuffer = event.inputBuffer.getChannelData(0);
                    
                    if (this.debugMode) {
                        const energy = this.calculateAudioEnergy(inputBuffer);
                        console.log(`🎤 捕获音频: ${inputBuffer.length}样本, 能量: ${energy.toFixed(6)}`);
                    }
                    
                    // 将新的音频数据添加到缓冲区（录制所有音频）
                    this.audioBuffer = this.appendToBuffer(this.audioBuffer, inputBuffer);
                    
                    // 按照40ms/1280字节的规格分片发送（包含所有噪音和静音）
                    this.processAudioChunks();
                }
            };
            
            // 连接音频处理链
            source.connect(this.processor);
            this.processor.connect(this.audioContext.destination);
            
            console.log('🎵 音频捕获已启动');
            
        } catch (error) {
            throw new Error(`音频捕获失败: ${error.message}`);
        }
    }
    
    appendToBuffer(oldBuffer, newData) {
        const combinedLength = oldBuffer.length + newData.length;
        const combined = new Float32Array(combinedLength);
        combined.set(oldBuffer, 0);
        combined.set(newData, oldBuffer.length);
        return combined;
    }
    
    processAudioChunks() {
        while (this.audioBuffer.length >= this.chunkSamples) {
            // 提取一个分片 (640 samples = 40ms)
            const chunk = this.audioBuffer.slice(0, this.chunkSamples);
            
            // 转换为PCM16格式并发送（发送所有音频，包含噪音和静音）
            const pcmData = this.convertToPCM16(chunk);
            
            // 发送音频数据 - 不进行任何过滤
            if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
                this.websocket.send(pcmData);
                
                if (this.debugMode) {
                    const energy = this.calculateAudioEnergy(chunk);
                    console.log(`📤 发送音频数据: ${pcmData.byteLength} bytes, 能量: ${energy.toFixed(6)}`);
                }
            }
            
            // 从缓冲区中移除已处理的数据
            this.audioBuffer = this.audioBuffer.slice(this.chunkSamples);
        }
    }
    
    calculateAudioEnergy(audioData) {
        if (!audioData || audioData.length === 0) return 0;
        
        let energy = 0;
        for (let i = 0; i < audioData.length; i++) {
            energy += audioData[i] * audioData[i];
        }
        return energy / audioData.length;
    }
    
    convertToPCM16(float32Array) {
        const buffer = new ArrayBuffer(float32Array.length * 2);
        const view = new DataView(buffer);
        
        for (let i = 0; i < float32Array.length; i++) {
            const sample = Math.max(-1, Math.min(1, float32Array[i]));
            view.setInt16(i * 2, sample * 0x7FFF, true);
        }
        
        return buffer;
    }
    
    handleMessage(data) {
        try {
            const result = JSON.parse(data);
            
            switch (result.type) {
                case 'result':
                    this.handleRecognitionResult(result);
                    break;
                case 'final_result':
                    this.handleFinalResult(result);
                    break;
                case 'error':
                    this.showError(`识别错误: ${result.message}`);
                    break;
            }
        } catch (error) {
            console.error('❌ 消息解析失败:', error);
        }
    }
    
    handleRecognitionResult(result) {
        const text = result.text || result.accumulated_text || '';
        if (text) {
            this.recognizedText = text;
            this.lastRecognizedText = text;  // 保存最后的识别文本
            this.updateVoiceText(text);
            this.updateVoiceMessage(text, false);
        }
    }
    
    handleFinalResult(result) {
        // 清除超时定时器
        if (this.finalResultTimeout) {
            clearTimeout(this.finalResultTimeout);
            this.finalResultTimeout = null;
        }
        
        this.waitingForFinal = false;
        
        const finalText = result.text || result.accumulated_text || '';
        const cleanText = this.cleanText(finalText);
        
        if (cleanText && cleanText.length >= 1) {
            console.log('✅ 识别完成:', cleanText);
            this.sendMessage(cleanText);
        } else {
            this.showError('未识别到有效内容');
        }
        
        this.cleanup();
    }
    
    handleTimeoutFinal() {
        console.log('⏰ 超时处理，使用最后识别的文本:', this.lastRecognizedText);
        
        this.waitingForFinal = false;
        this.finalResultTimeout = null;
        
        // 使用最后识别的文本作为最终结果
        const cleanText = this.cleanText(this.lastRecognizedText);
        
        if (cleanText && cleanText.length >= 1) {
            console.log('✅ 超时识别完成:', cleanText);
            this.sendMessage(cleanText);
        } else {
            this.showError('未识别到有效内容');
        }
        
        this.cleanup();
    }
    
    cleanText(text) {
        if (!text) return '';
        
        let cleaned = text.trim();
        cleaned = cleaned.replace(/\s+/g, ' ');
        cleaned = cleaned.replace(/^[，。、！？；：""''（）【】…—\s]+/, '');
        cleaned = cleaned.replace(/[，。、！？；：""''（）【】…—\s]+$/, '');
        
        return cleaned;
    }
    
    updateUI(isRecording) {
        if (isRecording) {
            this.voiceToggle.innerHTML = '<i class="ri-stop-line text-red-600"></i>';
            this.voiceToggle.className = 'w-10 h-10 rounded-full bg-red-100 hover:bg-red-200 flex items-center justify-center transition-colors !rounded-button';
            this.voiceIndicator?.classList.remove('hidden');
        } else {
            this.voiceToggle.innerHTML = '<i class="ri-mic-line text-gray-600"></i>';
            this.voiceToggle.className = 'w-10 h-10 rounded-full bg-gray-100 hover:bg-gray-200 flex items-center justify-center transition-colors !rounded-button';
            this.voiceIndicator?.classList.add('hidden');
        }
    }
    
    showPreview(show) {
        const preview = document.getElementById('voice-preview');
        if (preview) {
            preview.classList.toggle('hidden', !show);
        }
    }
    
    updateVoiceText(text) {
        const voiceText = document.getElementById('voice-text');
        if (voiceText) {
            voiceText.textContent = text || '等待语音输入...';
            voiceText.scrollTop = voiceText.scrollHeight;
        }
    }
    
    createVoiceMessage() {
        const messageId = 'voice-msg-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = messageId;
        messageDiv.className = 'message-slide-in mb-6';
        messageDiv.innerHTML = `
            <div class="flex justify-end">
                <div class="max-w-3xl bg-primary text-white rounded-lg p-4 shadow-sm">
                    <div class="flex items-center space-x-2 mb-2">
                        <i class="ri-mic-line text-white"></i>
                        <span class="text-sm">语音输入中...</span>
                        <div class="loading-dots">
                            <div class="dot bg-white"></div>
                            <div class="dot bg-white"></div>
                            <div class="dot bg-white"></div>
                        </div>
                    </div>
                    <div class="message-content">${this.recognizedText || '正在听取您的语音...'}</div>
                </div>
            </div>
        `;
        
        this.messagesContainer?.appendChild(messageDiv);
        this.currentMessageId = messageId;
        this.scrollToBottom();
    }
    
    updateVoiceMessage(text, isFinal) {
        if (!this.currentMessageId) return;
        
        const messageElement = document.getElementById(this.currentMessageId);
        const contentDiv = messageElement?.querySelector('.message-content');
        
        if (contentDiv) {
            contentDiv.textContent = text || '正在听取您的语音...';
        }
        
        // 更新状态显示
        const headerDiv = messageElement?.querySelector('.flex.items-center');
        if (headerDiv) {
            if (isFinal) {
                headerDiv.innerHTML = `
                    <i class="ri-check-line text-green-300"></i>
                    <span class="text-sm text-green-300">识别完成</span>
                `;
            } else if (this.waitingForFinal) {
                headerDiv.innerHTML = `
                    <i class="ri-time-line text-yellow-300"></i>
                    <span class="text-sm text-yellow-300">处理中...</span>
                `;
            }
        }
        
        this.scrollToBottom();
    }
    
    sendMessage(text) {
        if (!text?.trim()) return;
        
        // 先更新消息状态为完成
        this.updateVoiceMessage(text, true);
        
        // 设置到输入框
        if (this.messageInput) {
            this.messageInput.value = text.trim();
            
            // 触发发送
            if (window.sendLangGraphMessage) {
                window.sendLangGraphMessage();
            } else {
                this.sendButton?.click();
            }
            
            // 清空输入框
            setTimeout(() => {
                if (this.messageInput) {
                    this.messageInput.value = '';
                }
            }, 100);
        }
        
        this.currentMessageId = null;
    }
    
    showError(message) {
        console.error('❌ 语音错误:', message);
        
        // 清理错误的语音消息
        if (this.currentMessageId) {
            document.getElementById(this.currentMessageId)?.remove();
            this.currentMessageId = null;
        }
        
        // 显示错误提示
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 z-50 p-3 bg-red-50 border border-red-200 text-red-800 rounded-lg shadow-lg max-w-sm';
        errorDiv.innerHTML = `
            <div class="flex items-center space-x-2">
                <i class="ri-error-warning-line"></i>
                <span class="text-sm">${message}</span>
                <button onclick="this.parentNode.parentNode.remove()" class="ml-2 text-red-600 hover:text-red-800">
                    <i class="ri-close-line"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        setTimeout(() => errorDiv.remove(), 3000);
    }
    
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    cleanup() {
        this.isRecording = false;
        this.waitingForFinal = false;
        
        // 清除超时定时器
        if (this.finalResultTimeout) {
            clearTimeout(this.finalResultTimeout);
            this.finalResultTimeout = null;
        }
        
        // 清理音频缓冲区
        if (this.audioBuffer) {
            this.audioBuffer = new Float32Array(0);
        }
        
        // 关闭音频处理器
        if (this.processor) {
            this.processor.disconnect();
            this.processor = null;
        }
        
        // 关闭音频上下文
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
            this.audioContext = null;
        }
        
        // 关闭WebSocket
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }
        
        // 关闭音频流
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }
        
        // 重置状态
        this.recognizedText = '';
        this.lastRecognizedText = '';
        this.currentMessageId = null;
        
        // 更新UI
        this.updateUI(false);
        this.showPreview(false);
    }
    
    // 配置方法
    enableDebugMode(enabled = true) {
        this.debugMode = enabled;
        console.log(`🐛 调试模式: ${enabled ? '启用' : '禁用'}`);
    }
    
    setRecordAllAudio(enabled = true) {
        this.recordAllAudio = enabled;
        console.log(`🎤 完整音频录制: ${enabled ? '启用' : '禁用'}`);
    }
    
    // 获取当前配置
    getConfig() {
        return {
            recordAllAudio: this.recordAllAudio,
            debugMode: this.debugMode,
            isRecording: this.isRecording,
            backendSessionId: this.backendSessionId
        };
    }
    
    destroy() {
        this.cleanup();
        document.getElementById('voice-preview')?.remove();
        console.log('🧹 语音模块已销毁');
    }
}

// 全局变量
let simplifiedVoiceModule = null;

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    // 检查浏览器支持
    if (!navigator.mediaDevices?.getUserMedia || !window.WebSocket) {
        console.warn('⚠️ 浏览器不支持语音功能');
        return;
    }
    
    setTimeout(() => {
        try {
            simplifiedVoiceModule = new SimplifiedVoiceModule();
            window.simplifiedVoiceModule = simplifiedVoiceModule;
            console.log('✅ 简化语音模块已加载');
        } catch (error) {
            console.error('❌ 语音模块初始化失败:', error);
        }
    }, 1000);
});

// 页面卸载时清理
window.addEventListener('beforeunload', () => {
    simplifiedVoiceModule?.destroy();
});

// 导出
window.SimplifiedVoiceModule = SimplifiedVoiceModule;
