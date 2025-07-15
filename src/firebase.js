import { initializeApp } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-app.js";
import { getDatabase, ref, set, onValue } from "https://www.gstatic.com/firebasejs/9.6.1/firebase-database.js";

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

export { database, ref, set, onValue };
