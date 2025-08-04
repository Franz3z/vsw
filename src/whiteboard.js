// whiteboard.js (Ensure this is the latest, consolidated version from our discussion)

// Imports for Firebase (adjust paths if firebase.js is in a different location relative to this file)
import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js';
import { getDatabase, onValue, ref, set, push } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js';

// Firebase Config (as provided by you)
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
export const database = getDatabase(app); // Export database if other modules need it, otherwise 'const' is fine

// Global variables for whiteboard state
let canvas = null;
let ctx = null;
let drawing = false;
let current = { x: 0, y: 0 };
let whiteboardInitialized = false; // Flag to prevent re-initializing event listeners

// Helper function to get mouse position relative to canvas
function getMousePos(evt) {
    if (!canvas) return { x: 0, y: 0 }; // Defensive check
    const rect = canvas.getBoundingClientRect();
    return {
        x: evt.clientX - rect.left,
        y: evt.clientY - rect.top
    };
}

// Function to draw a line and optionally send to Firebase
function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
    if (!ctx) return; // Ensure context is available

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.lineJoin = 'round';
    ctx.lineCap = 'round';

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.closePath();

    if (!emit) return; // Don't re-emit if drawing from Firebase data

    const linesRef = ref(database, 'whiteboard/lines');
    push(linesRef, { x0, y0, x1, y1, color, timestamp: Date.now() })
        .catch(error => console.error("Error pushing line to Firebase:", error));
}


// Function to redraw all lines from Firebase
function redrawAllLinesFromFirebase() {
    // This listener ensures real-time updates and initial load
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        if (!ctx || !canvas) return; // Ensure canvas context is ready

        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear before redrawing all
        snapshot.forEach((childSnapshot) => {
            const data = childSnapshot.val();
            if (data && data.x0 !== undefined) {
                drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
            }
        });
    });
}


// --- Main Whiteboard Initialization Function ---
function initializeWhiteboard() {
    if (whiteboardInitialized) {
        // If already initialized, just ensure canvas dimensions are correct
        // and redraw if necessary (e.g., after modal was hidden)
        resizeCanvas();
        return;
    }

    canvas = document.getElementById('whiteboardCanvas');
    if (!canvas) {
        console.error("Whiteboard canvas element not found!");
        return;
    }
    ctx = canvas.getContext('2d');

    // Function to set canvas dimensions correctly and redraw content
    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);

        // ALWAYS RE-APPLY CONTEXT SETTINGS AFTER RESIZING
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        // Redraw content after resize
        redrawAllLinesFromFirebase();
    }

    // Set initial dimensions and add resize listener
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

    whiteboardInitialized = true; // Set flag AFTER all listeners are attached and canvas is ready
    console.log("Whiteboard initialized and listeners attached.");
}


// --- Global Functions (exposed to window for button clicks) ---

// This function will be called when the "Show Whiteboard" button is clicked
window.openWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'flex';
    // IMPORTANT: Call initializeWhiteboard() AFTER the modal is visible
    initializeWhiteboard();
    console.log("Whiteboard modal opened and initialization attempted.");
};

// This function will be called when the "Close" button is clicked
window.closeWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'none';
    console.log("Whiteboard modal closed.");
};

// This function will be called when the "Clear Whiteboard" button is clicked
window.clearWhiteboard = () => {
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    set(ref(database, 'whiteboard/lines'), null) // Clear data in Firebase
        .catch(error => console.error("Error clearing whiteboard in Firebase:", error));
    console.log("Whiteboard clear requested.");
};


// --- Event listeners for UI buttons (Run when DOM is fully loaded) ---
document.addEventListener('DOMContentLoaded', () => {
    const whiteboardToggleBtn = document.getElementById('whiteboardToggleBtn');
    const closeWhiteboardBtn = document.getElementById('closeWhiteboardBtn');
    const clearWhiteboardBtn = document.getElementById('clearWhiteboardBtn');

    if (whiteboardToggleBtn) {
        whiteboardToggleBtn.addEventListener('click', window.openWhiteboard);
        console.log("Whiteboard toggle button listener attached.");
    } else {
        console.warn("Whiteboard toggle button (ID: whiteboardToggleBtn) not found!");
    }

    if (closeWhiteboardBtn) {
        closeWhiteboardBtn.addEventListener('click', window.closeWhiteboard);
        console.log("Close whiteboard button listener attached.");
    } else {
        console.warn("Close whiteboard button (ID: closeWhiteboardBtn) not found!");
    }

    if (clearWhiteboardBtn) {
        clearWhiteboardBtn.addEventListener('click', window.clearWhiteboard);
        console.log("Clear whiteboard button listener attached.");
    } else {
        console.warn("Clear whiteboard button (ID: clearWhiteboardBtn) not found!");
    }
});
