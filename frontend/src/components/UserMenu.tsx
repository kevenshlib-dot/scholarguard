import { useState, useRef, useEffect } from "react";
import { useAuth } from "../contexts/AuthContext";

const roleLabels: Record<string, string> = {
  admin: "管理员",
  teacher: "教师",
  student: "学生",
  reviewer: "审核员",
  user: "用户",
};

const roleColors: Record<string, string> = {
  admin: "bg-purple-100 text-purple-700",
  teacher: "bg-blue-100 text-blue-700",
  student: "bg-green-100 text-green-700",
  reviewer: "bg-amber-100 text-amber-700",
  user: "bg-gray-100 text-gray-600",
};

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (!user) return null;

  const initials = user.username
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full px-2.5 py-2 rounded-xl hover:bg-gray-50 transition-all duration-200 text-left group"
      >
        <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-brand-500 to-brand-400 text-white flex items-center justify-center text-[11px] font-bold shrink-0 shadow-sm">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[13px] font-semibold text-gray-800 truncate">
            {user.username}
          </p>
          <p className="text-[11px] text-gray-400 truncate">
            {roleLabels[user.role] || user.role}
          </p>
        </div>
        <svg
          className={`w-3.5 h-3.5 text-gray-300 shrink-0 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2.5}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
        </svg>
      </button>

      {open && (
        <div className="absolute bottom-full left-0 right-0 mb-2 bg-white border border-gray-100 rounded-2xl shadow-xl shadow-gray-200/50 py-1 z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-50">
            <p className="text-xs text-gray-500 truncate">{user.email}</p>
            {user.organization_name && (
              <p className="text-xs text-gray-400 truncate mt-0.5">
                {user.organization_name}
              </p>
            )}
            <span className={`inline-block mt-2 text-[10px] font-bold px-2 py-0.5 rounded-md ${roleColors[user.role] || roleColors.user}`}>
              {roleLabels[user.role] || user.role}
            </span>
          </div>
          <button
            onClick={() => {
              setOpen(false);
              logout();
            }}
            className="w-full text-left px-4 py-2.5 text-sm text-red-500 hover:bg-red-50 transition-colors font-medium flex items-center gap-2"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            退出登录
          </button>
        </div>
      )}
    </div>
  );
}
