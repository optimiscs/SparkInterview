/**
 * 数字人系统诊断和修复工具
 * 检测并修复数字人SDK加载和初始化问题
 */

(function() {
    'use strict';
    
    console.log('🔧 数字人系统诊断工具启动');
    
    // 诊断结果对象
    const diagnosticResults = {
        sdk: false,
        manager: false,
        debug: false,
        platform: null,
        errors: []
    };
    
    /**
     * 检查SDK是否正确加载
     */
    function checkSDKLoading() {
        console.log('📋 步骤1: 检查SDK加载状态');
        
        // 检查主要SDK对象
        if (window.IAvatarPlatform || window.AvatarPlatform) {
            console.log('✅ 找到数字人SDK主对象');
            
            // 检查事件类型对象
            if (window.SDKEvents) {
                console.log('✅ 找到SDK事件类型对象');
                diagnosticResults.sdk = true;
                diagnosticResults.platform = 'IAvatarPlatform';
                return window.IAvatarPlatform || window.AvatarPlatform;
            } else {
                console.error('❌ SDK事件类型对象未找到');
                diagnosticResults.errors.push('SDK事件类型未加载');
                return null;
            }
        }
        
        console.error('❌ 未找到数字人SDK对象');
        diagnosticResults.errors.push('SDK未正确加载');
        return null;
    }
    
    /**
     * 尝试修复SDK加载问题
     */
    function fixSDKLoading() {
        console.log('🔧 尝试修复SDK加载问题');
        
        // 检查script标签是否存在
        const sdkScript = document.querySelector('script[src*="avatar-sdk-web"]');
        if (!sdkScript) {
            console.log('📜 数字人SDK script标签缺失，正在添加...');
            
            const script = document.createElement('script');
            script.src = './avatar-sdk-web_3.1.2.1002/index.js';
            script.onload = function() {
                console.log('✅ SDK脚本重新加载成功');
                setTimeout(runFullDiagnostic, 1000);
            };
            script.onerror = function() {
                console.error('❌ SDK脚本加载失败');
                tryAlternativeSDK();
            };
            document.head.appendChild(script);
            return;
        }
        
        console.log('📜 SDK script标签存在，检查路径是否正确');
        
        // 尝试重新加载
        const newScript = sdkScript.cloneNode(true);
        newScript.onload = function() {
            console.log('✅ SDK脚本重新加载成功');
            setTimeout(runFullDiagnostic, 1000);
        };
        newScript.onerror = function() {
            console.error('❌ SDK脚本重新加载失败');
            tryAlternativeSDK();
        };
        
        sdkScript.remove();
        document.head.appendChild(newScript);
    }
    
    /**
     * 尝试使用备用SDK文件
     */
    function tryAlternativeSDK() {
        console.log('🔄 尝试使用备用SDK文件');
        
        const alternativeFiles = [
            './avatar-sdk-web_3.1.2.1002/index-OS7Lza_r.js',
            './avatar-sdk-web_3.1.2.1002/webrtc-player--YuOiwFd.js',
            './avatar-sdk-web_3.1.2.1002/xrtc-player-BJTnVhG9.js'
        ];
        
        let currentIndex = 0;
        
        function tryNext() {
            if (currentIndex >= alternativeFiles.length) {
                console.error('❌ 所有备用SDK文件都无法加载');
                showManualInstructions();
                return;
            }
            
            const script = document.createElement('script');
            script.src = alternativeFiles[currentIndex];
            script.onload = function() {
                console.log(`✅ 备用SDK文件加载成功: ${alternativeFiles[currentIndex]}`);
                setTimeout(runFullDiagnostic, 1000);
            };
            script.onerror = function() {
                console.log(`❌ 备用SDK文件加载失败: ${alternativeFiles[currentIndex]}`);
                currentIndex++;
                tryNext();
            };
            document.head.appendChild(script);
        }
        
        tryNext();
    }
    
    /**
     * 检查管理器是否正确初始化
     */
    function checkManagerLoading() {
        console.log('📋 步骤2: 检查管理器初始化状态');
        
        if (typeof window.getAvatarManager === 'function') {
            console.log('✅ 数字人管理器函数存在');
            
            try {
                const manager = window.getAvatarManager();
                if (manager && typeof manager.init === 'function') {
                    console.log('✅ 数字人管理器实例正常');
                    diagnosticResults.manager = true;
                    return true;
                }
            } catch (e) {
                console.error('❌ 管理器实例化失败:', e);
                diagnosticResults.errors.push('管理器实例化失败: ' + e.message);
            }
        }
        
        console.error('❌ 数字人管理器未正确初始化');
        diagnosticResults.errors.push('管理器未初始化');
        return false;
    }
    
    /**
     * 检查调试助手是否加载
     */
    function checkDebugHelper() {
        console.log('📋 步骤3: 检查调试助手状态');
        
        if (window.avatarDebug && typeof window.avatarDebug.help === 'function') {
            console.log('✅ 调试助手正常加载');
            diagnosticResults.debug = true;
            return true;
        }
        
        console.error('❌ 调试助手未正确加载');
        diagnosticResults.errors.push('调试助手未加载');
        return false;
    }
    
    /**
     * 尝试手动初始化管理器
     */
    function manualInitializeManager() {
        console.log('🔧 尝试手动初始化管理器');
        
        const sdk = checkSDKLoading();
        if (!sdk) {
            console.error('❌ SDK未加载，无法初始化管理器');
            return false;
        }
        
        try {
            // 尝试创建管理器实例
            if (typeof window.AvatarIntegrationManager === 'function') {
                window.avatarManager = new window.AvatarIntegrationManager();
                
                if (window.avatarManager.init()) {
                    console.log('✅ 管理器手动初始化成功');
                    
                    // 重新绑定全局函数
                    window.getAvatarManager = function() {
                        return window.avatarManager;
                    };
                    
                    window.initializeAvatarSystem = async function() {
                        return window.avatarManager;
                    };
                    
                    return true;
                }
            }
        } catch (e) {
            console.error('❌ 手动初始化失败:', e);
            diagnosticResults.errors.push('手动初始化失败: ' + e.message);
        }
        
        return false;
    }
    
    /**
     * 显示手动修复说明
     */
    function showManualInstructions() {
        console.log('\n' + '='.repeat(50));
        console.log('📖 手动修复说明');
        console.log('='.repeat(50));
        console.log('1. 检查网络连接是否正常');
        console.log('2. 确认SDK文件路径是否正确');
        console.log('3. 尝试清除浏览器缓存后重新加载');
        console.log('4. 检查控制台是否有其他错误信息');
        console.log('5. 联系技术支持获取最新SDK版本');
        console.log('='.repeat(50));
    }
    
    /**
     * 运行完整诊断
     */
    function runFullDiagnostic() {
        console.log('\n🚀 开始数字人系统完整诊断');
        console.log('=' .repeat(40));
        
        // 检查SDK
        const sdkLoaded = checkSDKLoading();
        
        // 检查管理器
        const managerLoaded = checkManagerLoading();
        
        // 检查调试助手
        const debugLoaded = checkDebugHelper();
        
        // 输出诊断结果
        console.log('\n📊 诊断结果汇总:');
        console.log(`SDK加载: ${diagnosticResults.sdk ? '✅' : '❌'}`);
        console.log(`管理器: ${diagnosticResults.manager ? '✅' : '❌'}`);
        console.log(`调试助手: ${diagnosticResults.debug ? '✅' : '❌'}`);
        
        if (diagnosticResults.errors.length > 0) {
            console.log('\n❌ 发现的问题:');
            diagnosticResults.errors.forEach((error, index) => {
                console.log(`${index + 1}. ${error}`);
            });
        }
        
        // 尝试修复
        if (!diagnosticResults.sdk) {
            fixSDKLoading();
        } else if (!diagnosticResults.manager) {
            manualInitializeManager();
        }
        
        // 如果一切正常，测试功能
        if (diagnosticResults.sdk && diagnosticResults.manager) {
            console.log('\n🎉 系统诊断通过，准备测试功能...');
            setTimeout(testAvatarFunctions, 2000);
        }
    }
    
    /**
     * 测试数字人功能
     */
    function testAvatarFunctions() {
        console.log('\n🧪 开始功能测试');
        
        if (window.avatarDebug && typeof window.avatarDebug.testSpeak === 'function') {
            window.avatarDebug.testSpeak().then(result => {
                if (result) {
                    console.log('✅ 语音测试成功');
                } else {
                    console.log('⚠️ 语音测试未通过，可能需要连接配置');
                    window.avatarDebug.checkStatus && window.avatarDebug.checkStatus();
                }
            }).catch(error => {
                console.error('❌ 语音测试失败:', error);
            });
        } else {
            console.log('⚠️ 调试功能不可用，手动测试连接状态');
            
            try {
                const manager = window.getAvatarManager();
                const status = manager.getConnectionStatus();
                console.log('连接状态:', status);
            } catch (e) {
                console.error('状态检查失败:', e);
            }
        }
    }
    
    /**
     * 提供快速修复命令
     */
    window.avatarFix = {
        runDiagnostic: runFullDiagnostic,
        fixSDK: fixSDKLoading,
        initManager: manualInitializeManager,
        showHelp: showManualInstructions,
        testFunctions: testAvatarFunctions
    };
    
    // 自动运行诊断
    console.log('⏰ 3秒后自动开始诊断...');
    setTimeout(runFullDiagnostic, 3000);
    
    console.log('💡 您也可以手动运行以下命令:');
    console.log('- avatarFix.runDiagnostic() // 运行完整诊断');
    console.log('- avatarFix.fixSDK() // 修复SDK加载');
    console.log('- avatarFix.initManager() // 初始化管理器');
    console.log('- avatarFix.showHelp() // 显示帮助');
    
})();
