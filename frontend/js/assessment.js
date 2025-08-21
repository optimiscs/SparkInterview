// 评估联调脚本：通用题库渲染与作答提交
(function() {
  const qs = new URLSearchParams(location.search);
  const assessmentType = qs.get('type') || 'technical';
  const titleMap = {
    technical: '技术能力测试',
    communication: '沟通能力测试',
    logical_thinking: '逻辑思维测试',
    learning_ability: '学习能力测试',
    teamwork: '团队协作测试',
    innovation: '创新思维测试'
  };

  const el = (id) => document.getElementById(id);
  const $title = el('assessment-title');
  const $desc = el('assessment-desc');
  const $instructions = el('instructions');
  const $timeLimit = el('time-limit');
  const $start = el('start-btn');
  const $intro = el('intro-section');
  const $exam = el('exam-section');
  const $result = el('result-section');
  const $question = el('question-container');
  const $progress = el('progress-text');
  const $prev = el('prev-btn');
  const $next = el('next-btn');
  const $save = el('save-btn');
  const $submit = el('submit-btn');
  const $submitBar = el('submit-bar');
  const $toast = el('toast');
  const $timerText = el('timer-text');
  const $difficulty = el('difficulty-select');

  $title.textContent = titleMap[assessmentType] || '能力评估';
  $desc.textContent = '系统将为您加载题库，并在答题过程中自动保存。';

  let sessionId = null;
  let questions = [];
  let answers = {}; // questionId -> answer string
  let currentIndex = 0;
  let timeRemainSec = null;
  let timerHandle = null;

  function toast(msg) {
    $toast.textContent = msg;
    $toast.classList.remove('hidden');
    setTimeout(() => $toast.classList.add('hidden'), 2000);
  }

  function authHeaders() {
    return window.authManager.getAuthHeaders();
  }

  async function startAssessment() {
    try {
      const res = await fetch('/api/v1/start', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          assessment_type: assessmentType,
          user_id: window.authManager.user?.id || 'unknown',
          difficulty_level: $difficulty.value
        })
      });
      if (!res.ok) throw new Error('开始评估失败');
      const data = await res.json();
      sessionId = data.session_id;
      questions = data.questions || [];
      $instructions.textContent = data.instructions || '';
      $timeLimit.textContent = data.time_limit || 30;

      timeRemainSec = (data.time_limit || 30) * 60;
      updateTimer();
      timerHandle = setInterval(updateTimer, 1000);

      $intro.classList.add('hidden');
      $exam.classList.remove('hidden');
      currentIndex = 0;
      renderCurrent();
    } catch (e) {
      console.error(e);
      toast('启动失败，请先登录或稍后重试');
    }
  }

  function updateTimer() {
    if (timeRemainSec == null) return;
    const m = Math.max(0, Math.floor(timeRemainSec / 60));
    const s = Math.max(0, timeRemainSec % 60);
    $timerText.textContent = `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    if (timeRemainSec === 0) {
      clearInterval(timerHandle);
      doSubmit();
      return;
    }
    timeRemainSec -= 1;
  }

  function renderCurrent() {
    if (!questions.length) {
      $question.innerHTML = '<div class="text-gray-500">暂无题目</div>';
      return;
    }
    const q = questions[currentIndex];
    $progress.textContent = `${currentIndex+1}/${questions.length}`;

    let inner = '';
    inner += `<div class="flex items-center justify-between mb-3">
      <div class="flex items-center"><span class="px-2 py-1 bg-primary/10 text-primary text-xs rounded mr-2">${q.type}</span>
      <h2 class="text-lg font-medium text-gray-900">${escapeHtml(q.title)}</h2></div>
      </div>`;
    inner += `<p class="text-gray-700 mb-4">${escapeHtml(q.content)}</p>`;

    const saved = answers[q.id] || '';
    if (q.type === 'choice' && Array.isArray(q.options)) {
      inner += '<div class="space-y-2">';
      q.options.forEach((opt, i) => {
        const active = saved === opt ? 'active' : '';
        inner += `<div class="choice-item border border-gray-200 rounded-lg p-3 cursor-pointer ${active}" data-value="${escapeAttr(opt)}">
          <div class="flex items-center justify-between"><div class="text-gray-800">${escapeHtml(opt)}</div>
          <div class="w-5 h-5 flex items-center justify-center ${active? 'text-primary':'text-gray-300'}"><i class="ri-check-line"></i></div></div>
        </div>`;
      });
      inner += '</div>';
    } else if (q.type === 'essay') {
      const limit = q.max_words ? `最大字数 ${q.max_words}` : '';
      inner += `<textarea id="essay-input" class="w-full border border-gray-200 rounded-lg p-3 min-h-40" placeholder="请输入答案...">${escapeHtml(saved)}</textarea>
      <div class="text-xs text-gray-500 mt-1">${limit}</div>`;
    } else if (q.type === 'code') {
      inner += `<textarea id="code-input" class="w-full border border-gray-200 rounded-lg p-3 min-h-60 mono" placeholder="在此编写代码...">${escapeHtml(saved)}</textarea>
      <div class="text-xs text-gray-500 mt-1">可使用任意语言；提交后进行简要规则评分</div>`;
    } else {
      inner += '<div class="text-gray-500">暂不支持的题型</div>';
    }

    $question.innerHTML = inner;

    // 绑定交互
    if (q.type === 'choice') {
      $question.querySelectorAll('.choice-item').forEach(div => {
        div.addEventListener('click', () => {
          $question.querySelectorAll('.choice-item').forEach(d => d.classList.remove('active'));
          div.classList.add('active');
          answers[q.id] = div.getAttribute('data-value') || '';
        });
      });
    }

    // 控制按钮显隐
    $prev.disabled = currentIndex === 0;
    if (currentIndex === questions.length - 1) {
      $next.classList.add('hidden');
      $submitBar.classList.remove('hidden');
    } else {
      $next.classList.remove('hidden');
      $submitBar.classList.add('hidden');
    }
  }

  function collectCurrentAnswer() {
    if (!questions.length) return;
    const q = questions[currentIndex];
    if (q.type === 'essay') {
      const ta = document.getElementById('essay-input');
      if (ta) answers[q.id] = ta.value || '';
    } else if (q.type === 'code') {
      const ta = document.getElementById('code-input');
      if (ta) answers[q.id] = ta.value || '';
    }
  }

  async function saveCurrent() {
    try {
      collectCurrentAnswer();
      const q = questions[currentIndex];
      if (!q) return;
      const res = await fetch('/api/v1/answer', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ session_id: sessionId, question_id: q.id, answer: answers[q.id] || '' })
      });
      if (!res.ok) throw new Error('保存失败');
      toast('已保存');
    } catch (e) {
      console.error(e);
      toast('保存失败');
    }
  }

  async function doSubmit() {
    try {
      // 收集最后一题答案
      collectCurrentAnswer();
      const res = await fetch('/api/v1/submit', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ session_id: sessionId, answers })
      });
      if (!res.ok) throw new Error('提交失败');
      const data = await res.json();
      // 展示结果
      el('result-score').textContent = data.score;
      el('result-level').textContent = data.level;
      el('result-analysis').textContent = data.analysis;
      const sug = el('result-suggestions');
      sug.innerHTML = '';
      (data.suggestions || []).forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        sug.appendChild(li);
      });
      $exam.classList.add('hidden');
      $result.classList.remove('hidden');
    } catch (e) {
      console.error(e);
      toast('提交失败');
    }
  }

  // 事件绑定
  document.addEventListener('DOMContentLoaded', async () => {
    const auth = await window.authManager.init();
    if (!auth || !auth.authenticated) {
      toast('请先登录');
    }
    // 预加载说明（调用 start 前不可知，只展示标题）
    $instructions.textContent = `${titleMap[assessmentType] || '能力评估'}将开始，请选择难度后点击开始。`;
  });

  $start.addEventListener('click', startAssessment);

  $prev.addEventListener('click', async () => {
    await saveCurrent();
    if (currentIndex > 0) {
      currentIndex -= 1;
      renderCurrent();
    }
  });

  $next.addEventListener('click', async () => {
    await saveCurrent();
    if (currentIndex < questions.length - 1) {
      currentIndex += 1;
      renderCurrent();
    }
  });

  $save.addEventListener('click', saveCurrent);
  $submit.addEventListener('click', doSubmit);

  // 工具函数
  function escapeHtml(str) {
    if (typeof str !== 'string') return '';
    return str.replace(/[&<>"]+/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
  }
  function escapeAttr(str) {
    return escapeHtml(String(str)).replace(/"/g, '&quot;');
  }
})();


