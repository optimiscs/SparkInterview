document.addEventListener('DOMContentLoaded', function() {
const collapseToggle = document.getElementById('collapseToggle');
const analysisPanel = document.getElementById('analysisPanel');
const toggleIcon = collapseToggle.querySelector('i');
let isPanelOpen = true;
collapseToggle.addEventListener('click', function() {
isPanelOpen = !isPanelOpen;
if (isPanelOpen) {
analysisPanel.style.width = '24rem';
toggleIcon.style.transform = 'rotate(0deg)';
} else {
analysisPanel.style.width = '0';
toggleIcon.style.transform = 'rotate(180deg)';
}
});
});
