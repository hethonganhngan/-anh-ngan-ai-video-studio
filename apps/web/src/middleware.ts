import { NextResponse, type NextRequest } from "next/server";

/** Chuyển hướng về /login nếu chưa có cookie phiên (xác thực thật vẫn do API kiểm tra). */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  if (pathname.startsWith("/login") || pathname.startsWith("/_next") || pathname === "/runtime-config.js" || pathname.startsWith("/favicon")) {
    return NextResponse.next();
  }
  if (!req.cookies.get("an_access")) {
    const url = req.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname)}`;
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = { matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"] };
