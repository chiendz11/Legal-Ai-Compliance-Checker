import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { mockEnabled } from "./shared/env";
import "./styles.css";

async function start() {
  if (mockEnabled) {
    const { worker } = await import("./mocks/browser");
    await worker.start({ onUnhandledRequest: "bypass", quiet: true });
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}

void start();
