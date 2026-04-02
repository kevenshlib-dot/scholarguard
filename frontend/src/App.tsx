import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import AdminRoute from "./components/AdminRoute";
import UserMenu from "./components/UserMenu";
import DetectPage from "./pages/detect/DetectPage";
import HistoryPage from "./pages/detect/HistoryPage";
import DetectReportPage from "./pages/detect/DetectReportPage";
import SuggestPage from "./pages/suggest/SuggestPage";
import ReviewPage from "./pages/review/ReviewPage";
import TranslatePage from "./pages/translate/TranslatePage";
import AdminPage from "./pages/admin/AdminPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";

interface NavItem {
  to: string;
  label: string;
  status: "active" | "demo" | "coming";
  icon: React.ReactNode;
  adminOnly?: boolean;
}

/* ── SVG icons (lightweight, consistent stroke style) ── */
const IconDetect = () => (
  <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
  </svg>
);
const IconSuggest = () => (
  <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
  </svg>
);
const IconReview = () => (
  <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z" />
  </svg>
);
const IconTranslate = () => (
  <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.233.038 3.334.114M9 5.25V3m3.334 2.364C11.176 10.658 7.69 15.08 3 17.502m9.334-12.138c.896.061 1.785.147 2.666.257m-4.589 8.495a18.023 18.023 0 01-3.827-5.802" />
  </svg>
);
const IconAdmin = () => (
  <svg className="w-[18px] h-[18px]" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const allNavItems: NavItem[] = [
  { to: "/detect", label: "AI 检测", status: "active", icon: <IconDetect /> },
  { to: "/suggest", label: "写作建议", status: "active", icon: <IconSuggest /> },
  { to: "/review", label: "复核中心", status: "active", icon: <IconReview /> },
  { to: "/translate", label: "翻译润色", status: "coming", icon: <IconTranslate /> },
  { to: "/admin", label: "系统管理", status: "active", icon: <IconAdmin />, adminOnly: true },
];

function AppLayout() {
  const { user } = useAuth();
  const navItems = allNavItems.filter(
    (item) => !item.adminOnly || user?.role === "admin"
  );

  return (
    <div className="flex h-screen bg-[#f1f5f9]">
      {/* Sidebar */}
      <aside className="w-[260px] bg-white/80 backdrop-blur-xl border-r border-gray-200/60 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-5 py-5">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-400 flex items-center justify-center text-white font-bold text-lg shadow-lg shadow-brand-500/30">
              S
            </div>
            <div>
              <h1 className="text-[15px] font-bold text-gray-900 leading-tight tracking-tight">
                ScholarGuard
              </h1>
              <p className="text-[11px] text-gray-400 font-medium">
                学术 AI 检测平台
              </p>
            </div>
          </div>
        </div>

        {/* Section label */}
        <div className="px-5 pt-2 pb-1">
          <p className="text-[10px] font-bold text-gray-300 uppercase tracking-[0.15em]">
            功能导航
          </p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-1 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : "text-gray-500 hover:text-gray-700"}`
              }
            >
              <span className="w-5 flex items-center justify-center shrink-0">{item.icon}</span>
              <span className="flex-1">{item.label}</span>
              {item.status === "coming" && (
                <span className="text-[9px] font-semibold text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded-md">
                  Soon
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Menu */}
        <div className="px-3 py-2 border-t border-gray-100/80">
          <UserMenu />
        </div>

        {/* Footer */}
        <div className="px-5 py-3 text-[10px] text-gray-300">
          <p className="font-semibold">ScholarGuard v1.0</p>
          <p className="mt-0.5">AI4SS Lab</p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <Routes>
          <Route path="/" element={<Navigate to="/detect" replace />} />
          <Route path="/detect" element={<DetectPage />} />
          <Route path="/detect/history" element={<HistoryPage />} />
          <Route path="/detect/report" element={<DetectReportPage />} />
          <Route path="/suggest" element={<SuggestPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/translate" element={<TranslatePage />} />
          <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Public routes — no sidebar */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* Protected routes — with sidebar layout */}
        <Route
          path="/*"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        />
      </Routes>
    </AuthProvider>
  );
}
