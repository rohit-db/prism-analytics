import { createContext, useContext } from "react";
import type { AppConfig, Content } from "./appConfig";
import type { Brand } from "@/theme/brand";

export const AppConfigContext = createContext<AppConfig | null>(null);

export function useAppConfig(): AppConfig {
  const cfg = useContext(AppConfigContext);
  if (!cfg) throw new Error("useAppConfig must be used within <AppConfigProvider>");
  return cfg;
}

/** Runtime brand (falls back to the bundled copy when /api/config is unreachable). */
export function useBrand(): Brand {
  return useAppConfig().brand;
}

/** Runtime user-facing copy. */
export function useContent(): Content {
  return useAppConfig().content;
}
