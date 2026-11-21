import { createRoot } from "react-dom/client";
import { AuthWindow } from "./AuthWindow";
import "./style.css";
import "./typography.css";
import "./interface.css";
import { restoreMotionPreference } from "./motion";
restoreMotionPreference();
createRoot(document.getElementById("root")!).render(<AuthWindow />);
