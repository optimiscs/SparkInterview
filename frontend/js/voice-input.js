document.addEventListener('DOMContentLoaded', function() {
const voiceToggle = document.getElementById('voiceToggle');
const voiceIndicator = document.getElementById('voiceIndicator');
const messageInput = document.getElementById('messageInput');
let isRecording = false;
voiceToggle.addEventListener('click', function() {
isRecording = !isRecording;
if (isRecording) {
voiceToggle.innerHTML = '<i class="ri-mic-fill text-red-500"></i>';
voiceToggle.classList.add('bg-red-100');
voiceIndicator.classList.remove('hidden');
messageInput.style.opacity = '0.3';
} else {
voiceToggle.innerHTML = '<i class="ri-mic-line text-gray-600"></i>';
voiceToggle.classList.remove('bg-red-100');
voiceIndicator.classList.add('hidden');
messageInput.style.opacity = '1';
}
});
});
