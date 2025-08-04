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
let whiteboardInitialized = false; // Flag to prevent re-initialization


// Helper function to get mouse position relative to canvas
function getMousePos(evt) {
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
        console.log("Whiteboard already initialized.");
        return; // Prevent re-initializing if already done
    }

    canvas = document.getElementById('whiteboardCanvas');
    if (!canvas) {
        console.error("Whiteboard canvas element not found!");
        return;
    }
    ctx = canvas.getContext('2d');

    // Function to set canvas dimensions correctly
    function resizeCanvas() {
        // Ensure canvas CSS width/height are set (e.g., width: 100%; height: 500px;)
        // Then set internal canvas resolution to match its displayed size
        const rect = canvas.getBoundingClientRect();
        canvas.width = rect.width;
        canvas.height = rect.height;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);
        // Redraw content after resize if necessary (e.g., fetch all lines and redraw)
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

    // --- Firebase Listeners ---
    // Listen for all lines on the whiteboard
    function redrawAllLinesFromFirebase() {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear before redrawing
        onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
            // This listener will trigger on initial load and any change to 'whiteboard/lines'
            ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear again just in case (e.g., on initial load)
            snapshot.forEach((childSnapshot) => {
                const data = childSnapshot.val();
                if (data && data.x0 !== undefined) {
                    // Draw without emitting back to Firebase
                    drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
                }
            });
        });
    }
    redrawAllLinesFromFirebase(); // Call initially to load existing lines

    // Listener for clearing the whiteboard via Firebase update
    // This is optional if your 'clearWhiteboard' function directly sets 'whiteboard/lines' to null
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        // If the 'lines' node is removed (e.g., by clearWhiteboard), this will be null
        if (!snapshot.exists()) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        }
    });

    whiteboardInitialized = true; // Set flag after successful initialization
}


// --- Global Functions (exposed to window) ---
// This function can be called from your HTML to open the modal and initialize whiteboard
window.openWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'flex';
    initializeWhiteboard(); // Call initialize when opening the modal
};

window.closeWhiteboard = () => {
    document.getElementById('whiteboardModal').style.display = 'none';
    // Optionally, if you want to stop listeners when modal closes:
    // This would require storing the unsubscribe function from onValue.
    // For simplicity, we'll keep them running for now.
};

window.clearWhiteboard = () => {
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
    // Set 'whiteboard/lines' to null to clear all data
    set(ref(database, 'whiteboard/lines'), null) // Changed from {} to null to fully remove node
        .catch(error => console.error("Error clearing whiteboard in Firebase:", error));
};


// --- Event listeners for UI buttons ---
document.addEventListener('DOMContentLoaded', () => {
    const whiteboardToggleBtn = document.getElementById('whiteboardToggleBtn');
    const closeWhiteboardBtn = document.getElementById('closeWhiteboardBtn');
    const clearWhiteboardBtn = document.getElementById('clearWhiteboardBtn');

    if (whiteboardToggleBtn) {
        whiteboardToggleBtn.addEventListener('click', window.openWhiteboard);
    } else {
        console.warn("Whiteboard toggle button not found!");
    }

    if (closeWhiteboardBtn) {
        closeWhiteboardBtn.addEventListener('click', window.closeWhiteboard);
    } else {
        console.warn("Close whiteboard button not found!");
    }

    if (clearWhiteboardBtn) {
        clearWhiteboardBtn.addEventListener('click', window.clearWhiteboard);
    } else {
        console.warn("Clear whiteboard button not found!");
    }
});
