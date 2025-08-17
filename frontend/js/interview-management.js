// 新建面试按钮事件处理
document.addEventListener('DOMContentLoaded', function() {
    const newInterviewBtn = document.getElementById('new-interview-btn');
    if (newInterviewBtn) {
        newInterviewBtn.addEventListener('click', async function() {
            try {
                // 禁用按钮防止重复点击
                this.disabled = true;
                this.innerHTML = '<i class="ri-loader-line animate-spin"></i><span>创建中...</span>';
                
                await createNewChatSession();
                
            } catch (error) {
                console.error('创建新面试失败:', error);
                showError('创建新面试失败: ' + error.message);
            } finally {
                // 恢复按钮状态
                this.disabled = false;
                this.innerHTML = '<i class="ri-add-line"></i><span>新建面试</span>';
            }
        });
    }
});
