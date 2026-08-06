import { useState } from "react";
import { useBrand } from "@/appconfig/useAppConfig";
import { cn } from "@/lib/utils";

export function BrandLogo({
  variant,
  className,
}: {
  variant: "full" | "mark";
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  // Runtime brand, so a config-only re-skin updates the logo/monogram too.
  const brand = useBrand();
  const src = variant === "full" ? brand.identity.logo : brand.identity.logoMark;
  const mono = brand.identity.shortName.slice(0, 1).toUpperCase();

  if (failed || !src) {
    return (
      <span
        className={cn(
          "grid place-items-center rounded-md bg-primary text-primary-foreground font-semibold shadow-db-lg",
          className
        )}
      >
        {mono}
      </span>
    );
  }
  return (
    <img
      src={src}
      alt={brand.identity.appName}
      onError={() => setFailed(true)}
      className={className}
    />
  );
}
