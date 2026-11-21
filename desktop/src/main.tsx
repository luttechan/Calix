import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./style.css";
import "./typography.css";
import "./interface.css";
import "./select.css";
import "./checklist.css";
import { restoreMotionPreference } from "./motion";

restoreMotionPreference();
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
