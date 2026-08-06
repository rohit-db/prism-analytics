import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "./index.css";
import App from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";
import { RegistryProvider } from "./registry/RegistryProvider";
import { AppConfigProvider } from "./appconfig/AppConfigProvider";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AppConfigProvider>
          <RegistryProvider>
            <App />
          </RegistryProvider>
        </AppConfigProvider>
      </ThemeProvider>
    </BrowserRouter>
  </StrictMode>
);
