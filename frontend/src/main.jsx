import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

// No StrictMode: its dev double-mount re-inits MapLibre/Cesium twice and spams
// benign "getSource of undefined" errors from the discarded first map instance.
ReactDOM.createRoot(document.getElementById("root")).render(<App />);
