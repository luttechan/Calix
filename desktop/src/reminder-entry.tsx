import React from "react";
import { createRoot } from "react-dom/client";
import { ReminderWindow } from "./ReminderWindow";
import "./style.css";
import "./typography.css";
import "./interface.css";
import { restoreMotionPreference } from "./motion";
restoreMotionPreference();
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ReminderWindow />
  </React.StrictMode>,
);
