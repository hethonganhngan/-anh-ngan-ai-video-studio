import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const vnd = new Intl.NumberFormat("vi-VN");
export const formatVND = (v: number | string | null | undefined) =>
  v === null || v === undefined || v === "" ? "—" : `${vnd.format(Math.round(Number(v)))} ₫`;
export const formatNumber = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "—" : new Intl.NumberFormat("vi-VN", { maximumFractionDigits: digits }).format(v);
export const formatDate = (v: string | null | undefined, withTime = true) => {
  if (!v) return "—";
  const d = new Date(v);
  return new Intl.DateTimeFormat("vi-VN", {
    day: "2-digit", month: "2-digit", year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    timeZone: "Asia/Ho_Chi_Minh",
  }).format(d);
};
export const formatBytes = (b: number) =>
  b < 1024 ? `${b} B` : b < 1048576 ? `${(b / 1024).toFixed(1)} KB` : `${(b / 1048576).toFixed(1)} MB`;
export const shortId = (id?: string | null) => (id ? id.slice(0, 8) : "—");
