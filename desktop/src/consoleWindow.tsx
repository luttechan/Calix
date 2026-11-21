import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { ConsoleView, emptyConsole, type ConsoleAction, type ConsoleState } from "./ConsoleView";

function ConsoleWindow() {
  const [state, setState] = useState(emptyConsole);
  const [error, setError] = useState("");
  const act = (action: ConsoleAction) => {
    void invoke("developer_console_action", { action })
      .catch(() => setError("Calix Console connection unavailable."));
  };
  useEffect(() => {
    let active = true;
    const registered = listen<ConsoleState>("developer-console:update", (event) => {
      if (active) {
        setError("");
        setState(event.payload);
      }
    });
    void registered.then(() => {
      if (active) act("ready");
    }).catch(() => setError("Calix Console connection unavailable."));
    return () => {
      active = false;
      void registered.then((unlisten) => unlisten()).catch(() => {});
    };
  }, []);
  return <ConsoleView state={error ? { ...state, error } : state} onAction={act} />;
}

createRoot(document.getElementById("root")!).render(<ConsoleWindow />);
