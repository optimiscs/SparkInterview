<template>
  <div class="xrtc-container">
    <div class="video-area">
      <div class="wrapperPlayer"></div>
    </div>
    <div class="chat-area">
      <div class="chat-box">
        <div
          v-for="(msg, idx) in chatList"
          :key="idx"
          :class="['msg-row', msg.role]"
        >
          <div class="msg-bubble">
            <span class="avatar" v-if="msg.role === 'user'">🧑</span>
            <span class="avatar" v-else>🤖</span>
            <span class="msg-text">{{ msg.text }}</span>
          </div>
        </div>
      </div>
      <div class="input-area">
        <input
          v-model="userInput"
          placeholder="请输入你的问题"
          @keyup.enter="sendQuestion"
        />
        <button @click="sendQuestion">发送</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { RTCPlayer } from './rtcplayer2.1.3/rtcplayer.esm.js'

let player
const streamInfo = ref(null)
const userInput = ref('')
const chatList = ref([])
let ws = null
let hasPlayed = false

onMounted(() => {
  player = new RTCPlayer()
  ws = new WebSocket('ws://localhost:8765')
  ws.onopen = () => {
    console.log('WebSocket已连接')
  }
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    if (msg.type === 'stream') {
      streamInfo.value = msg.data
    }
  }
})

// 不再自动 play，改为用户交互时 play
function play() {
  if (!streamInfo.value) {
    console.error('streamInfo is null')
    return
  }
  player
    .on('play', () => console.log('play事件'))
    .on('playing', () => console.log('playing事件'))
    .on('waiting', () => console.log('waiting事件'))
    .on('error', (e) => console.log('error:', e))
    .on('not-allowed', () => player.resume())

  player.playerType = 12
  player.stream = { ...streamInfo.value }
  player.videoSize = { width: 360, height: 640 }
  player.container = document.querySelector('.wrapperPlayer')
  player.play()
}

function sendQuestion() {
  const text = userInput.value.trim()
  if (ws && ws.readyState === 1 && text) {
    // 首次发送时先 play
    if (!hasPlayed) {
      play()
      hasPlayed = true
      // 延迟发送，确保 play 已经触发
      setTimeout(() => {
        ws.send(JSON.stringify({ type: 'driverText', data: text }))
      }, 300)
    } else {
      ws.send(JSON.stringify({ type: 'driverText', data: text }))
    }
    chatList.value.push({ role: 'user', text })
    userInput.value = ''
  }
}
</script>

<style scoped>
.xrtc-container {
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: flex-start;
  gap: 32px;
  padding: 40px 0;
  background: #f2f3f7;
  min-height: 100vh;
}

.video-area {
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  padding: 24px;
}

.wrapperPlayer {
  height: 480px;
  width: 270px;
  background: linear-gradient(135deg, #e3eafc 0%, #f7fafd 100%);
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chat-area {
  width: 350px;
  display: flex;
  flex-direction: column;
  background: #fff;
  border-radius: 24px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  padding: 24px 20px 16px 20px;
}

.chat-box {
  flex: 1;
  max-height: 400px;
  overflow-y: auto;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.msg-row {
  display: flex;
  align-items: flex-end;
}

.msg-row.user {
  justify-content: flex-end;
}

.msg-row.ai {
  justify-content: flex-start;
}

.msg-bubble {
  display: flex;
  align-items: center;
  max-width: 80%;
  padding: 10px 16px;
  border-radius: 18px;
  font-size: 16px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  word-break: break-word;
  transition: background 0.2s;
}

.msg-row.user .msg-bubble {
  background: linear-gradient(135deg, #e0eaff 0%, #f7fafd 100%);
  color: #222;
  border-bottom-right-radius: 6px;
  margin-right: 8px;
}

.msg-row.ai .msg-bubble {
  background: #f1f2f6;
  color: #007aff;
  border-bottom-left-radius: 6px;
  margin-left: 8px;
}

.avatar {
  font-size: 20px;
  margin-right: 8px;
  margin-left: 0;
}

.msg-row.user .avatar {
  order: 2;
  margin-left: 8px;
  margin-right: 0;
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: center;
  background: #f7f8fa;
  border-radius: 12px;
  padding: 8px 12px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.03);
}

input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 16px;
  padding: 8px 0;
  color: #222;
}

button {
  background: linear-gradient(135deg, #007aff 0%, #4f8cff 100%);
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 8px 20px;
  font-size: 16px;
  cursor: pointer;
  transition: background 0.2s;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

button:hover {
  background: linear-gradient(135deg, #005ecb 0%, #357ae8 100%);
}
</style>