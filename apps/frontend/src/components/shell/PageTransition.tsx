"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

// Route-change motion without a dependency: re-key the wrapper on the pathname so
// React remounts it, replaying a CSS entrance. Cheap, interruptible, and honours
// prefers-reduced-motion (the keyframe is disabled in globals.css). One
// orchestrated reveal per navigation reads as "an app", not a stack of pages.
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div key={pathname} className="page-enter">
      {children}
    </div>
  );
}
