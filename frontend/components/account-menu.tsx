"use client";

import { useEffect, useRef, useState } from "react";
import { supabase } from "@/lib/supabase";

// Top-right account control: shows the signed-in email and a dropdown with
// sign-out. Closes on outside pointer-down and on Escape.
export function AccountMenu({ email }: { email: string }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const initial = email.trim().charAt(0).toUpperCase() || "?";

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="group inline-flex items-center gap-2 rounded-full border border-black/15 py-1 pl-1 pr-2.5 transition-colors hover:bg-black/5 dark:border-white/20 dark:hover:bg-white/10"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-foreground text-[12px] font-semibold text-background">
          {initial}
        </span>
        <span className="hidden max-w-[180px] truncate text-[13px] font-medium sm:block">
          {email}
        </span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          aria-hidden
          className={"opacity-50 transition-transform " + (open ? "rotate-180" : "")}
        >
          <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-60 origin-top-right overflow-hidden rounded-2xl border border-black/10 bg-background p-1.5 shadow-xl dark:border-white/15"
        >
          <div className="px-3 pb-2 pt-2">
            <span className="block text-[10px] uppercase tracking-widest opacity-50">
              Signed in as
            </span>
            <span className="mt-1 block truncate text-[13.5px] font-medium">{email}</span>
          </div>
          <div aria-hidden className="my-1 h-px bg-black/10 dark:bg-white/15" />
          <button
            type="button"
            role="menuitem"
            onClick={() => supabase().auth.signOut()}
            className="inline-flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-[13.5px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/10"
          >
            <svg
              width="16"
              height="16"
              viewBox="0 0 16 16"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              aria-hidden
              className="opacity-60"
            >
              <path
                d="M6 14H3.5A1.5 1.5 0 0 1 2 12.5v-9A1.5 1.5 0 0 1 3.5 2H6M10.5 11 14 7.5 10.5 4M14 7.5H6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
