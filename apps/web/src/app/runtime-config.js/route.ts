/** Cấu hình runtime (không cần build lại khi đổi môi trường). API_PUBLIC_URL rỗng = cùng origin qua reverse proxy. */
export const dynamic = "force-dynamic";

export function GET() {
  const url = process.env.API_PUBLIC_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "";
  return new Response(`window.__ANNGAN_API_URL__=${JSON.stringify(url)};`, {
    headers: { "Content-Type": "application/javascript; charset=utf-8", "Cache-Control": "no-store" },
  });
}
