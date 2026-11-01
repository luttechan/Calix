import React from "react";
import { createRoot } from "react-dom/client";
import { ReminderWindow } from "./ReminderWindow";
import "./style.css";
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ReminderWindow />
  </React.StrictMode>,
);
