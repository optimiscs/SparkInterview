/**
 * 数字人系统快速测试脚本
 * 用于验证修复后的系统是否正常工作
 */

(function() {
    'use strict';
    
    console.log('🧪 数字人快速测试脚本加载');
    
    // 测试配置
    const testConfig = {
        timeout: 10000, // 10秒超时
        retryCount: 3,
        currentRetry: 0
    };
    
    /**
     * 运行快速测试
     */
    function runQuickTest() {
        console.log('🚀 开始数字人系统快速测试');
        console.log('⏰ 超时时间:', testConfig.timeout + 'ms');
        
        const startTime = Date.now();
        
        // 测试步骤
        const tests = [
            { name: 'SDK加载检查', fn: testSDKLoading },
            { name: '管理器初始化检查', fn: testManagerInit },
            { name: '配置验证', fn: testConfiguration },
            { name: '连接功能测试', fn: testConnection }
        ];
        
        let currentTest = 0;
        
        function runNextTest() {
            if (currentTest >= tests.length) {
                console.log(`🎉 所有测试完成! 总耗时: ${Date.now() - startTime}ms`);
                showTestResults();
                return;
            }
            
            const test = tests[currentTest];
            console.log(`📋 测试 ${currentTest + 1}/${tests.length}: ${test.name}`);
            
            try {
                const result = test.fn();
                if (result === true) {
                    console.log(`✅ ${test.name} 通过`);
                    currentTest++;
                    setTimeout(runNextTest, 100);
                } else if (result && typeof result.then === 'function') {
                    // 异步测试
                    result.then(() => {
                        console.log(`✅ ${test.name} 通过`);
                        currentTest++;
                        setTimeout(runNextTest, 100);
                    }).catch(error => {
                        console.error(`❌ ${test.name} 失败:`, error);
                        handleTestFailure(test);
                    });
                } else {
                    console.error(`❌ ${test.name} 失败`);
                    handleTestFailure(test);
                }
            } catch (error) {
                console.error(`❌ ${test.name} 异常:`, error);
                handleTestFailure(test);
            }
        }
        
        function handleTestFailure(test) {
            if (testConfig.currentRetry < testConfig.retryCount) {
                testConfig.currentRetry++;
                console.log(`🔄 重试 ${test.name} (${testConfig.currentRetry}/${testConfig.retryCount})`);
                setTimeout(() => {
                    runNextTest();
                }, 1000);
            } else {
                console.error(`❌ ${test.name} 最终失败，跳过后续测试`);
                showTestResults();
            }
        }
        
        // 开始测试
        runNextTest();
        
        // 设置总超时
        setTimeout(() => {
            console.error('⏰ 测试超时，可能存在严重问题');
            showTestResults();
        }, testConfig.timeout);
    }
    
    /**
     * 测试SDK加载
     */
    function testSDKLoading() {
        const sdkObjects = ['IAvatarPlatform', 'AvatarPlatform'];
        
        for (const objName of sdkObjects) {
            if (typeof window[objName] !== 'undefined') {
                console.log(`✅ 找到SDK对象: ${objName}`);
                return true;
            }
        }
        
        throw new Error('SDK对象未找到');
    }
    
    /**
     * 测试管理器初始化
     */
    function testManagerInit() {
        if (typeof window.getAvatarManager !== 'function') {
            throw new Error('getAvatarManager函数不存在');
        }
        
        try {
            const manager = window.getAvatarManager();
            if (!manager || typeof manager.init !== 'function') {
                throw new Error('管理器实例无效');
            }
            
            console.log('✅ 管理器实例正常');
            return true;
        } catch (error) {
            throw new Error('管理器初始化失败: ' + error.message);
        }
    }
    
    /**
     * 测试配置
     */
    function testConfiguration() {
        try {
            const manager = window.getAvatarManager();
            const config = manager.config;
            
            if (!config || !config.apiInfo) {
                throw new Error('配置信息不完整');
            }
            
            const required = ['appId', 'apiKey', 'apiSecret', 'serverUrl', 'sceneId'];
            for (const key of required) {
                if (!config.apiInfo[key]) {
                    throw new Error(`缺少必要配置: ${key}`);
                }
            }
            
            console.log('✅ 配置验证通过');
            return true;
        } catch (error) {
            throw new Error('配置验证失败: ' + error.message);
        }
    }
    
    /**
     * 测试连接功能
     */
    function testConnection() {
        return new Promise((resolve, reject) => {
            try {
                const manager = window.getAvatarManager();
                const status = manager.getConnectionStatus();
                
                console.log('🔗 当前连接状态:', status);
                
                // 这里不实际连接，只测试连接方法是否存在
                if (typeof manager.connect === 'function' || typeof manager.start === 'function') {
                    console.log('✅ 连接方法可用');
                    resolve();
                } else {
                    reject(new Error('连接方法不可用'));
                }
            } catch (error) {
                reject(error);
            }
        });
    }
    
    /**
     * 显示测试结果
     */
    function showTestResults() {
        console.log('\n' + '='.repeat(50));
        console.log('📊 数字人系统快速测试报告');
        console.log('='.repeat(50));
        
        // 检查调试助手是否可用
        if (window.avatarDebug) {
            console.log('🔧 调试助手可用，您可以使用以下命令:');
            console.log('- avatarDebug.help() // 显示帮助');
            console.log('- avatarDebug.checkStatus() // 检查状态');
            console.log('- avatarDebug.testSpeak() // 测试语音');
        } else {
            console.log('⚠️ 调试助手不可用');
        }
        
        // 检查修复工具是否可用
        if (window.avatarFix) {
            console.log('🛠️ 修复工具可用，您可以使用以下命令:');
            console.log('- avatarFix.runDiagnostic() // 运行诊断');
            console.log('- avatarFix.fixSDK() // 修复SDK');
        } else {
            console.log('⚠️ 修复工具不可用');
        }
        
        console.log('\n💡 如果测试失败，请:');
        console.log('1. 刷新页面重试');
        console.log('2. 检查网络连接');
        console.log('3. 查看控制台错误信息');
        console.log('4. 使用修复工具 avatarFix.runDiagnostic()');
        console.log('='.repeat(50));
    }
    
    /**
     * 等待DOM和其他脚本加载完成后运行测试
     */
    function startWhenReady() {
        if (document.readyState === 'complete') {
            setTimeout(runQuickTest, 2000);
        } else {
            window.addEventListener('load', () => {
                setTimeout(runQuickTest, 2000);
            });
        }
    }
    
    // 导出测试函数到全局
    window.avatarQuickTest = {
        run: runQuickTest,
        testSDK: testSDKLoading,
        testManager: testManagerInit,
        testConfig: testConfiguration,
        testConnection: testConnection
    };
    
    console.log('💡 您可以手动运行测试: avatarQuickTest.run()');
    
    // 自动开始测试
    startWhenReady();
    
})();
