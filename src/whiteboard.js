// whiteboard.js (Revised for HTML-based initialization)

// Imports for Firebase
import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js';
import { getDatabase, onValue, ref, set, push } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js';

// Firebase Config
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
export const database = getDatabase(app); // Export database if needed elsewhere

// Global variables for whiteboard state (these are local to this module)
let canvas = null;
let ctx = null;
let drawing = false;
let current = { x: 0, y: 0 };
let whiteboardInitialized = false; // Flag to prevent re-initializing canvas listeners

// Helper function to get mouse position relative to canvas
function getMousePos(evt) {
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
        x: evt.clientX - rect.left,
        y: evt.clientY - rect.top
    };
}

// Function to draw a line and optionally send to Firebase
function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
    if (!ctx) return;

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.closePath();

    if (!emit) return;

    const linesRef = ref(database, 'whiteboard/lines');
    push(linesRef, { x0, y0, x1, y1, color, timestamp: Date.now() })
        .catch(error => console.error("Error pushing line to Firebase:", error));
}

// Function to redraw all lines from Firebase
function redrawAllLinesFromFirebase() {
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        if (!ctx || !canvas) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        snapshot.forEach((childSnapshot) => {
            const data = childSnapshot.val();
            if (data && data.x0 !== undefined) {
                drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
            }
        });
    });
}

// --- Main Whiteboard Initialization Function (exported) ---
// This function must be called from HTML when the whiteboard is opened
export function initializeWhiteboard() { // EXPORT THIS FUNCTION
    if (whiteboardInitialized) {
        resizeCanvas(); // Ensure canvas is correctly sized if already initialized
        return;
    }

    canvas = document.getElementById('whiteboardCanvas');
    if (!canvas) {
        console.error("Whiteboard canvas element not found!");
        return;
    }
    ctx = canvas.getContext('2d');

    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);

        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        redrawAllLinesFromFirebase();
    }

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // --- Canvas Event Listeners ---
    canvas.addEventListener('mousedown', (e) => {
        drawing = true;
        const pos = getMousePos(e);
        current.x = pos.x;
        current.y = pos.y;
    });

    canvas.addEventListener('mouseup', () => { drawing = false; });
    canvas.addEventListener('mouseout', () => { drawing = false; });

    canvas.addEventListener('mousemove', (e) => {
        if (!drawing) return;
        const pos = getMousePos(e);
        drawLine(current.x, current.y, pos.x, pos.y);
        current.x = pos.x;
        current.y = pos.y;
    });

    // Listener for clearing the whiteboard via Firebase update
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        if (!snapshot.exists() && ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    });

    whiteboardInitialized = true;
    console.log("Whiteboard initialized and listeners attached.");
}

// --- Export clearWhiteboard for HTML to call directly ---
export function clearWhiteboard() { // EXPORT THIS FUNCTION
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    set(ref(database, 'whiteboard/lines'), null)
        .catch(error => console.error("Error clearing whiteboard in Firebase:", error));
    console.log("Whiteboard clear requested.");
}

// Note: closeWhiteboard doesn't need to be in whiteboard.js unless it does whiteboard-specific cleanup.
// It's just a modal display function.
