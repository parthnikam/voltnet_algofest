"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "outline" | "ghost";
  size?: "default" | "sm" | "lg";
};

export function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-xl border text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40 disabled:pointer-events-none disabled:opacity-50",
        variant === "default" &&
          "border-white bg-white text-black hover:bg-zinc-200",
        variant === "outline" &&
          "border-white/15 bg-white/[0.03] text-white hover:bg-white/[0.08]",
        variant === "ghost" &&
          "border-transparent bg-transparent text-zinc-300 hover:bg-white/[0.06] hover:text-white",
        size === "default" && "h-11 px-4",
        size === "sm" && "h-9 px-3 text-xs",
        size === "lg" && "h-12 px-5 text-base",
        className,
      )}
      {...props}
    />
  );
}
