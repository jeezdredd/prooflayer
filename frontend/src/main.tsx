import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import SplashGate from "./components/ui/SplashGate";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SplashGate>
      <App />
    </SplashGate>
  </React.StrictMode>
);
