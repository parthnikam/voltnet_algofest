import * as React from "react";

import { cn } from "@/lib/utils";

export function Select({
  className,
  children,
  ...props
}: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "flex h-11 w-full rounded-xl border border-white/10 bg-black px-3 text-sm text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
