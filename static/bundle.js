import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js';
import { getDatabase, onValue, ref, set } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js';

const firebaseConfig = {
  apiKey: "AIzaSyB5G7A9MDFgojI6sf86UNBgJWU2nLrzzD4",
  authDomain: "virtual-student-workspace.firebaseapp.com",
  databaseURL: "https://virtual-student-workspace-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "virtual-student-workspace",
  storageBucket: "virtual-student-workspace.appspot.com",
  messagingSenderId: "282960097196",
  appId: "1:282960097196:web:95aeb40a96d78902ac5409",
  measurementId: "G-9F77DKB2FH"
};

const app = initializeApp(firebaseConfig);
const database = getDatabase(app);

let canvas, ctx, drawing, current;

function initializeWhiteboard() {
    canvas = document.getElementById('whiteboardCanvas');
    ctx = canvas.getContext('2d');
    drawing = false;
    current = { x: 0, y: 0 };
    
    function resizeCanvas() {
        canvas.width = canvas.clientWidth;
        canvas.height = canvas.clientHeight;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);
    }
    
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Rest of the whiteboard functionality...
    function getMousePos(evt) {
      const rect = canvas.getBoundingClientRect();
      return {
        x: evt.clientX - rect.left,
        y: evt.clientY - rect.top
      };
    }

    function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
      // ... existing implementation ...
    }

    canvas.addEventListener('mousedown', (e) => {
      drawing = true;
      const pos = getMousePos(e);
      current.x = pos.x;
      current.y = pos.y;
    });

    canvas.addEventListener('mouseup', () => drawing = false);
    canvas.addEventListener('mouseout', () => drawing = false);

    canvas.addEventListener('mousemove', (e) => {
      if (!drawing) return;
      const pos = getMousePos(e);
      drawLine(current.x, current.y, pos.x, pos.y);
      current.x = pos.x;
      current.y = pos.y;
    });

    onValue(ref(database, 'whiteboard/last_line'), (snapshot) => {
      const data = snapshot.val();
      if (data && data.x0 !== undefined) {
        drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
      }
    });

    onValue(ref(database, 'whiteboard'), (snapshot) => {
      const data = snapshot.val();
      if (!data || Object.keys(data).length === 0) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    });
}

window.initializeWhiteboard = initializeWhiteboard;
window.clearWhiteboard = () => {
  if (ctx) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  set(ref(database, 'whiteboard'), {});
};

function getMousePos(evt) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: evt.clientX - rect.left,
    y: evt.clientY - rect.top
  };
}

function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(x0, y0);
  ctx.lineTo(x1, y1);
  ctx.stroke();
  ctx.closePath();

  if (!emit) return;

  const lineData = { x0, y0, x1, y1, color };
  set(ref(database, 'whiteboard/last_line'), lineData);
}

canvas.addEventListener('mousedown', (e) => {
  drawing = true;
  const pos = getMousePos(e);
  current.x = pos.x;
  current.y = pos.y;
});

canvas.addEventListener('mouseup', () => drawing = false);
canvas.addEventListener('mouseout', () => drawing = false);

canvas.addEventListener('mousemove', (e) => {
  if (!drawing) return;
  const pos = getMousePos(e);
  drawLine(current.x, current.y, pos.x, pos.y);
  current.x = pos.x;
  current.y = pos.y;
});

onValue(ref(database, 'whiteboard/last_line'), (snapshot) => {
  const data = snapshot.val();
  if (data && data.x0 !== undefined) {
    drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
  }
});

onValue(ref(database, 'whiteboard'), (snapshot) => {
  const data = snapshot.val();

  if (!data || Object.keys(data).length === 0) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
});

window.clearWhiteboard = () => {
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  set(ref(database, 'whiteboard'), {});
};

