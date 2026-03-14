import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

function parseTs(ts: string): Date {
  const d = new Date(ts);
  if (!isNaN(d.getTime())) return d;
  return new Date(ts + "Z");
}

export function timeAgo(ts: string): string {
  if (!ts) return "";
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return "";
  const sec = Math.floor((Date.now() - d.getTime()) / 1000);
  if (sec < 0) return "just now";
  if (sec < 60) return `${sec}s ago`;
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return `${Math.floor(sec / 86400)}d ago`;
}

export function fmtTime(ts: string): string {
  if (!ts) return "";
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleString();
}

export function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
