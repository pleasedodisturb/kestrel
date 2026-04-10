import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Map a numeric score to Tailwind color classes based on high/mid thresholds. */
export function scoreColor(value: number, high: number, mid: number): string {
  if (value >= high) return "bg-green-100 text-green-800";
  if (value >= mid) return "bg-yellow-100 text-yellow-800";
  return "bg-red-100 text-red-800";
}
