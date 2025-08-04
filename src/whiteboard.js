// whiteboard.js
// Make sure these imports match your actual Firebase SDK URLs
import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js';
import { getDatabase, onValue, ref, set, push } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js'; // Added 'push'

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
export const database = getDatabase(app); // Export database for other modules if needed


let canvas = null;
let ctx = null;
let drawing = false;
let current = { x: 0, y: 0 };
let whiteboardInitialized = false; // Flag to prevent re-initializing event listeners


// Helper function to get mouse position relative to canvas
function getMousePos(evt) {
    // Make sure 'canvas' is not null when this is called
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
        x: evt.clientX - rect.left,
        y: evt.clientY - rect.top
    };
}

// Draw line on canvas (local drawing and emitting to Firebase)
function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
    if (!ctx) return; // Ensure context is available

    ctx.strokeStyle = color;
    ctx.lineWidth = 2; // Keep line width consistent
    ctx.lineJoin = 'round'; // Smooth line joins
    ctx.lineCap = 'round'; // Smooth line caps

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.closePath();

    if (!emit) return; // Don't re-emit if drawing from Firebase data

    // Use 'push' to create a unique ID for each line segment
    const linesRef = ref(database, 'whiteboard/lines'); // Store lines under 'lines' node
    push(linesRef, { x0, y0, x1, y1, color, timestamp: Date.now() })
        .catch(error => console.error("Error pushing line to Firebase:", error));
}


// --- Main Whiteboard Initialization Function ---
function initializeWhiteboard() {
    if (whiteboardInitialized) {
        // If already initialized, just ensure canvas dimensions are correct
        // and redraw if necessary (e.g., after modal was hidden)
        resizeCanvas(); // Important: resize even if already initialized
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
        // Ensure canvas CSS width/height are set (e.g., width: 100%; height: 500px;)
        // Then set internal canvas resolution to match its displayed size
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);

        // ALWAYS RE-APPLY CONTEXT SETTINGS AFTER RESIZING
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        // Redraw content after resize from Firebase
        redrawAllLinesFromFirebase();
    }

    // Set initial dimensions and add resize listener
    resizeCanvas(); // Call on initial init
    window.addEventListener('resize', resizeCanvas); // Listen for window resize


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

    // --- Firebase Listeners ---
    // Listen for all lines on the whiteboard
    function redrawAllLinesFromFirebase() {
        // No need to clear here, as onValue will trigger a clear initially
        onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
            // This listener will trigger on initial load and any change to 'whiteboard/lines'
            // Clear the canvas fully before redrawing all lines
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            snapshot.forEach((childSnapshot) => {
                const data = childSnapshot.val();
                if (data && data.x0 !== undefined) {
                    // Draw without emitting back to Firebase
                    drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
                }
            });
        });
    }
    // No need to call redrawAllLinesFromFirebase() here, as it's within the resizeCanvas()
    // and the onValue listener itself will trigger on initial data.

    // Listener for clearing the whiteboard via Firebase update
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        // If the 'lines' node is removed (e.g., by clearWhiteboard), this will be null
        if (!snapshot.exists() && ctx) { // Ensure ctx exists before clearing
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    });

    whiteboardInitialized = true; // Set flag AFTER all listeners are attached and canvas is ready
}


// --- Global Functions (exposed to window) ---
// This function can be called from your HTML to open the modal and initialize whiteboard
window.openWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'flex';
    // IMPORTANT: Call initializeWhiteboard() AFTER the modal is visible
    // This ensures the canvas has its final dimensions and is ready for drawing.
    initializeWhiteboard();
};

window.closeWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'none';
};

window.clearWhiteboard = () => {
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    // Set 'whiteboard/lines' to null to clear all data
    set(ref(database, 'whiteboard/lines'), null) // Changed from {} to null to fully remove node
        .catch(error => console.error("Error clearing whiteboard in Firebase:", error));
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
        console.warn("Whiteboard toggle button not found!");
    }

    if (closeWhiteboardBtn) {
        closeWhiteboardBtn.addEventListener('click', window.closeWhiteboard);
        console.log("Close whiteboard button listener attached.");
    } else {
        console.warn("Close whiteboard button not found!");
    }

    if (clearWhiteboardBtn) {
        clearWhiteboardBtn.addEventListener('click', window.clearWhiteboard);
        console.log("Clear whiteboard button listener attached.");
    } else {
        console.warn("Clear whiteboard button not found!");
    }

    // Optional: If you want whiteboard to be initialized immediately on page load
    // (e.g., if canvas is always visible), call initializeWhiteboard() here.
    // However, if it's in a modal, calling it when modal opens is usually better.
    // initializeWhiteboard();
});
