import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
const startup = {
  name: "calix-startup",
  transformIndexHtml: {
    order: "pre" as const,
    handler: (html: string, context: { filename: string }) =>
      ["login.html", "reminder.html", "reminder-probe.html"].some((name) =>
        context.filename.endsWith(name),
      )
        ? html
        : html.replace(
            "<body>",
            `<body><style>${readFileSync(new URL("./src/startup.css", import.meta.url), "utf8")}</style>${readFileSync(new URL("./public-startup.html", import.meta.url), "utf8")}`,
          ),
  },
};
export default defineConfig({
  define: {
    __CALIX_VERSION__: JSON.stringify(
      JSON.parse(
        readFileSync(new URL("./package.json", import.meta.url), "utf8"),
      ).version,
    ),
  },
  plugins: [startup, react()],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    watch: { ignored: ["**/.build/**", "**/src-tauri/**"] },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5174",
        headers: { "X-Calix-Token": process.env.CALIX_DEV_TOKEN || "" },
      },
    },
  },
  build: {
    target: "es2022",
    rolldownOptions: {
      input: {
        main: fileURLToPath(new URL("./index.html", import.meta.url)),
        reminder: fileURLToPath(new URL("./reminder.html", import.meta.url)),
        reminderProbe: fileURLToPath(
          new URL("./reminder-probe.html", import.meta.url),
        ),
        login: fileURLToPath(new URL("./login.html", import.meta.url)),
      },
    },
  },
  envPrefix: ["VITE_", "TAURI_ENV_"],
});
