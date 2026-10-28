import {
  LayoutDashboard, FolderKanban, Bot, Clapperboard, FileText, UserRound, Film, Scissors, ShieldCheck,
  RefreshCcw, GraduationCap, Megaphone, Library, Tv, Settings, type LucideIcon,
} from "lucide-react";

export type NavItem = { code: string; href: string; label: string; icon: LucideIcon; perm: string };
export type NavGroup = { label: string; items: NavItem[] };

export const NAV: NavGroup[] = [
  { label: "Điều hành", items: [
    { code: "M01", href: "/dashboard", label: "Dashboard CEO", icon: LayoutDashboard, perm: "dashboard.view" },
    { code: "M11", href: "/projects", label: "Quản lý dự án", icon: FolderKanban, perm: "project.view" },
    { code: "M14", href: "/agents", label: "AI Agent Control Center", icon: Bot, perm: "agent.view" },
  ] },
  { label: "Sản xuất", items: [
    { code: "M02", href: "/create", label: "Tạo video", icon: Clapperboard, perm: "project.create" },
    { code: "M03", href: "/scripts", label: "AI Script & Storyboard", icon: FileText, perm: "project.view" },
    { code: "M04", href: "/characters", label: "Character & Voice", icon: UserRound, perm: "character.view" },
    { code: "M05", href: "/production", label: "Video Production", icon: Film, perm: "project.view" },
    { code: "M06", href: "/editor", label: "AI Video Editor", icon: Scissors, perm: "project.view" },
  ] },
  { label: "Chất lượng", items: [
    { code: "M07", href: "/quality", label: "Quality Control", icon: ShieldCheck, perm: "qc.view" },
    { code: "M08", href: "/feedback", label: "Feedback Loop 360°", icon: RefreshCcw, perm: "feedback.view" },
    { code: "M09", href: "/lessons", label: "AI Lessons Learned", icon: GraduationCap, perm: "lesson.view" },
  ] },
  { label: "Nội dung", items: [
    { code: "M10", href: "/publishing", label: "Publishing & Analytics", icon: Megaphone, perm: "publish.view" },
    { code: "M12", href: "/library", label: "Thư viện tài nguyên", icon: Library, perm: "asset.view" },
    { code: "M13", href: "/channels", label: "Kênh & Brand DNA", icon: Tv, perm: "channel.view" },
  ] },
  { label: "Hệ thống", items: [
    { code: "M15", href: "/settings", label: "Cài đặt & quản trị", icon: Settings, perm: "admin.settings" },
  ] },
];

export const ALL_SCREENS = NAV.flatMap((g) => g.items);
