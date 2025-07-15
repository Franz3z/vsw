import { database, ref, set, onValue } from './firebase.js';

const canvas = document.getElementById('whiteboardCanvas');
const ctx = canvas.getContext('2d');
let drawing = false;

// Draw line on canvas
function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
  ctx.strokeStyle = color;
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.lineTo(x1, y1);
  ctx.stroke();
  ctx.closePath();

  if (!emit) return;

  const lineData = { x0, y0, x1, y1, color };
  set(ref(database, 'whiteboard/last_line'), lineData);
}

// Mouse events
let current = {};

canvas.addEventListener('mousedown', e => {
  drawing = true;
  current.x = e.offsetX;
  current.y = e.offsetY;
});

canvas.addEventListener('mouseup', () => { drawing = false; });
canvas.addEventListener('mouseout', () => { drawing = false; });

canvas.addEventListener('mousemove', e => {
  if (!drawing) return;
  drawLine(current.x, current.y, e.offsetX, e.offsetY);
  current.x = e.offsetX;
  current.y = e.offsetY;
});

// Listen to Firebase for new lines
onValue(ref(database, 'whiteboard/last_line'), (snapshot) => {
  const data = snapshot.val();
  if (data) {
    drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
  }
});

// Clear whiteboard
window.clearWhiteboard = () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  set(ref(database, 'whiteboard/last_line'), {});
};
