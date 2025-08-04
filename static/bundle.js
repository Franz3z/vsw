// Corrected bundle.js

// --- Firebase Initialization ---
import { initializeApp } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js';
import { getDatabase, onValue, ref, set, push } from 'https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js';

// Your Firebase Configuration
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
const database = getDatabase(app); // Database instance for Firebase Realtime Database

// --- Whiteboard State Variables ---
let canvas = null;
let ctx = null;
let drawing = false;
let current = { x: 0, y: 0 };
let whiteboardInitialized = false; // Flag to prevent re-initializing event listeners

// --- Helper Functions ---

/**
 * Calculates the mouse position relative to the canvas.
 * @param {MouseEvent} evt - The mouse event object.
 * @returns {{x: number, y: number}} - The x and y coordinates relative to the canvas.
 */
function getMousePos(evt) {
    if (!canvas) return { x: 0, y: 0 }; // Defensive check
    const rect = canvas.getBoundingClientRect();
    return {
        x: evt.clientX - rect.left,
        y: evt.clientY - rect.top
    };
}

/**
 * Draws a line on the canvas and optionally sends it to Firebase.
 * @param {number} x0 - Start X coordinate.
 * @param {number} y0 - Start Y coordinate.
 * @param {number} x1 - End X coordinate.
 * @param {number} y1 - End Y coordinate.
 * @param {string} color - Line color (e.g., 'black', '#FF0000').
 * @param {boolean} emit - True if the line should be sent to Firebase, false otherwise.
 */
function drawLine(x0, y0, x1, y1, color = 'black', emit = true) {
    if (!ctx) return; // Ensure context is available

    ctx.strokeStyle = color;
    ctx.lineWidth = 2; // Consistent line width
    ctx.lineJoin = 'round'; // Smooth line joins
    ctx.lineCap = 'round'; // Smooth line caps

    ctx.beginPath();
    ctx.moveTo(x0, y0);
    ctx.lineTo(x1, y1);
    ctx.stroke();
    ctx.closePath();

    if (!emit) return; // Don't re-emit if drawing from Firebase data (received from other users)

    // Use `push` to add a new unique entry for each line, preserving drawing history
    const linesRef = ref(database, 'whiteboard/lines');
    push(linesRef, { x0, y0, x1, y1, color, timestamp: Date.now() })
        .catch(error => console.error("Error pushing line to Firebase:", error));
}

/**
 * Redraws all lines from Firebase onto the canvas.
 * This function also sets up the real-time listener for new lines.
 */
function redrawAllLinesFromFirebase() {
    // This listener will trigger on initial load and any change to 'whiteboard/lines'
    onValue(ref(database, 'whiteboard/lines'), (snapshot) => {
        if (!ctx || !canvas) { // Ensure canvas context is ready before drawing
            console.warn("Canvas context not ready for redrawAllLinesFromFirebase.");
            return;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear the canvas fully before redrawing all lines
        snapshot.forEach((childSnapshot) => {
            const data = childSnapshot.val();
            if (data && data.x0 !== undefined) {
                // Draw without emitting back to Firebase (to prevent infinite loops)
                drawLine(data.x0, data.y0, data.x1, data.y1, data.color, false);
            }
        });
        console.log("Redrew all lines from Firebase.");
    });
}

// --- Main Whiteboard Initialization Function ---
// This function sets up the canvas, context, and attaches event listeners.
// It's designed to be called when the whiteboard modal becomes visible.
function initializeWhiteboard() {
    // Prevent re-initializing canvas listeners if already done
    if (whiteboardInitialized) {
        resizeCanvas(); // Just ensure dimensions are correct and redraw
        return;
    }

    canvas = document.getElementById('whiteboardCanvas');
    if (!canvas) {
        console.error("Whiteboard canvas element not found with ID 'whiteboardCanvas'!");
        return;
    }
    ctx = canvas.getContext('2d');

    /**
     * Resizes the canvas to match its displayed CSS size and redraws content.
     */
    function resizeCanvas() {
        const rect = canvas.getBoundingClientRect(); // Get actual rendered size
        canvas.width = rect.width;
        canvas.height = rect.height;
        console.log("Canvas resized to:", canvas.width, "x", canvas.height);

        // ALWAYS RE-APPLY CONTEXT SETTINGS AFTER RESIZING (canvas state resets)
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';

        // Redraw existing content to fit new dimensions
        redrawAllLinesFromFirebase();
    }

    // Set initial dimensions and add resize listener to keep canvas responsive
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);


    // --- Canvas Event Listeners for Drawing ---
    canvas.addEventListener('mousedown', (e) => {
        drawing = true;
        const pos = getMousePos(e);
        current.x = pos.x;
        current.y = pos.y;
    });

    canvas.addEventListener('mouseup', () => { drawing = false; });
    canvas.addEventListener('mouseout', () => { drawing = false; }); // Stop drawing if mouse leaves canvas area

    canvas.addEventListener('mousemove', (e) => {
        if (!drawing) return;
        const pos = getMousePos(e);
        drawLine(current.x, current.y, pos.x, pos.y);
        current.x = pos.x;
        current.y = pos.y;
    });

    whiteboardInitialized = true; // Mark as initialized after setup
    console.log("Whiteboard functionality fully initialized and listeners attached.");
}

// --- Global Functions (exposed to the window object for HTML to call) ---

/**
 * Opens the whiteboard modal and initializes the whiteboard canvas.
 * This function is exposed globally to be called by a button's click event.
 */
window.openWhiteboard = () => {
    const whiteboardModal = document.getElementById('whiteboardModal');
    if (whiteboardModal) {
        whiteboardModal.style.display = 'flex'; // Show the modal
        // IMPORTANT: Call initializeWhiteboard() AFTER the modal is visible
        // This ensures canvas dimensions are correctly calculated.
        initializeWhiteboard();
        console.log("Whiteboard modal opened, attempting initialization.");
    } else {
        console.error("Whiteboard modal element not found with ID 'whiteboardModal'!");
    }
};

/**
 * Closes the whiteboard modal.
 * This function is exposed globally.
 */
window.closeWhiteboard = () => {
    const whiteboardModal = document.getElementById('whiteboardModal');
    if (whiteboardModal) {
        whiteboardModal.style.display = 'none'; // Hide the modal
        console.log("Whiteboard modal closed.");
    }
};

/**
 * Clears the whiteboard canvas and removes all lines from Firebase.
 * This function is exposed globally.
 */
window.clearWhiteboard = () => {
    if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height); // Clear local canvas immediately
    }
    // Set Firebase 'whiteboard/lines' node to null to remove all stored lines
    set(ref(database, 'whiteboard/lines'), null)
        .catch(error => console.error("Error clearing whiteboard in Firebase:", error));
    console.log("Whiteboard clear action initiated in Firebase.");
};

// --- Event listeners for UI buttons (attached when the DOM is fully loaded) ---
// This ensures that button elements exist before trying to attach listeners.
document.addEventListener('DOMContentLoaded', () => {
    const whiteboardToggleBtn = document.getElementById('whiteboardToggleBtn');
    const closeWhiteboardBtn = document.getElementById('closeWhiteboardBtn');
    const clearWhiteboardBtn = document.getElementById('clearWhiteboardBtn');

    // Attach click listeners to the buttons
    if (whiteboardToggleBtn) {
        whiteboardToggleBtn.addEventListener('click', window.openWhiteboard);
        console.log("Listener attached to whiteboardToggleBtn.");
    } else {
        console.warn("whiteboardToggleBtn (ID: 'whiteboardToggleBtn') not found in DOM!");
    }

    if (closeWhiteboardBtn) {
        closeWhiteboardBtn.addEventListener('click', window.closeWhiteboard);
        console.log("Listener attached to closeWhiteboardBtn.");
    } else {
        console.warn("closeWhiteboardBtn (ID: 'closeWhiteboardBtn') not found in DOM!");
    }

    if (clearWhiteboardBtn) {
        clearWhiteboardBtn.addEventListener('click', window.clearWhiteboard);
        console.log("Listener attached to clearWhiteboardBtn.");
    } else {
        console.warn("clearWhiteboardBtn (ID: 'clearWhiteboardBtn') not found in DOM!");
    }
});
