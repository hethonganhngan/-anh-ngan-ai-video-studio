/** Chuyển prompt 9 mục của cảnh thành 1 đoạn văn để dán vào ô "Bạn muốn tạo những gì?" của Google Flow. */
export const FLOW_URL_DEFAULT = "https://flow.google.com/project/6ae396ef-7905-495b-90b1-564042d940cd";

const strip = (v: string) => v
  .replace(/\[(Character|Scene) Lock[^\]]*\]/g, "")
  .replace(/\b(CHR|SCN)-\d{4}-\d{4}\s*/g, "")
  .replace(/\s+/g, " ").trim().replace(/[.;,]$/, "");

export function toFlowPrompt(promptText: string, durationSec: number): string {
  const parts: Record<string, string> = {};
  for (const m of promptText.matchAll(/^\[\d+\.\s*([^\]]+)\]\s*(.*)$/gm)) parts[m[1].trim().toUpperCase()] = m[2];
  const get = (k: string) => strip(parts[k] ?? "");
  // Ngoại hình/trang phục lấy theo ảnh nhân vật gắn trên Flow (không theo Character Lock dạng chữ, dễ lệch ảnh)
  const [who, ...rest] = get("NHÂN VẬT").split(":");
  const manner = rest.join(":").split(";")[0].trim() || "ấm áp, nhẹ nhàng";
  const out = [
    `Video dọc 9:16, ${durationSec} giây, chuyển động tự nhiên, chân thực.`,
    `Nhân vật: ${who || "Nhân vật"}, giữ nguyên khuôn mặt và trang phục theo ảnh nhân vật đã gắn; thần thái ${manner}.`,
    get("LOẠI CẢNH") && `Kiểu cảnh: ${get("LOẠI CẢNH")}.`,
    get("HÀNH ĐỘNG") && `Hành động: ${get("HÀNH ĐỘNG")}.`,
    get("BỐI CẢNH") && `Bối cảnh: ${get("BỐI CẢNH")}.`,
    get("MÁY QUAY") && `Máy quay: ${get("MÁY QUAY")}.`,
    get("ÁNH SÁNG") && `Ánh sáng: ${get("ÁNH SÁNG")}.`,
    get("ÂM THANH") && `Âm thanh: ${get("ÂM THANH")}.`,
    get("THOẠI") && `Thoại tiếng Việt, giọng miền Nam chậm rãi, phát âm tròn chữ: ${get("THOẠI").replace(/\s*\/\s*/g, " ")}`,
    get("NEGATIVE PROMPT") && `Tránh: ${get("NEGATIVE PROMPT")}.`,
  ];
  return out.filter(Boolean).join(" ");
}
