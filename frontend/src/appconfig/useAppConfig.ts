import { createContext, useContext } from "react";
import type { AppConfig, Content } from "./appConfig";
import { bundledAppConfig } from "./appConfig";
import type { Brand } from "@/theme/brand";

export const AppConfigContext = createContext<AppConfig | null>(null);

/**
 * The runtime config, falling back to the bundled copy when no provider is mounted.
 *
 * Deliberately does NOT throw: brand identity is presentation, so a component rendered
 * outside the provider (an isolated unit test, a future standalone widget) should still
 * paint with the built-in brand rather than crash the tree.
 */
export function useAppConfig(): AppConfig {
  return useContext(AppConfigContext) ?? bundledAppConfig;
}

/** Runtime brand (falls back to the bundled copy when /api/config is unreachable). */
export function useBrand(): Brand {
  return useAppConfig().brand;
}

/** Runtime user-facing copy. */
export function useContent(): Content {
  return useAppConfig().content;
}
