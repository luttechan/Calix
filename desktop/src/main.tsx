import React from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { ReminderWindow } from "./Reminders";
import "./style.css";
const reminder = new URLSearchParams(location.search).has("reminder");
if (reminder) {
  document.getElementById("calix-startup")?.remove();
  document.getElementById("root")?.removeAttribute("inert");
  document.body.classList.add("reminder-surface");
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {reminder ? <ReminderWindow /> : <App />}
  </React.StrictMode>,
);
