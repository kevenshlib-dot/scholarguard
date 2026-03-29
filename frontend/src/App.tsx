import { Routes, Route, NavLink, Navigate } from "react-router-dom";
import { AuthProvider } from "./contexts/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";
import UserMenu from "./components/UserMenu";
import DetectPage from "./pages/detect/DetectPage";
import HistoryPage from "./pages/detect/HistoryPage";
import SuggestPage from "./pages/suggest/SuggestPage";
import ReviewPage from "./pages/review/ReviewPage";
import ResearchPage from "./pages/research/ResearchPage";
import TranslatePage from "./pages/translate/TranslatePage";
import AdminPage from "./pages/admin/AdminPage";
import LoginPage from "./pages/auth/LoginPage";
import RegisterPage from "./pages/auth/RegisterPage";

interface NavItem {
  to: string;
  label: string;
  status: "active" | "demo" | "coming";
  icon: string;
}

const navItems: NavItem[] = [
  { to: "/detect", label: "AI检测", status: "active", icon: "🔍" },
  { to: "/suggest", label: "写作建议", status: "active", icon: "✍️" },
  { to: "/review", label: "复核中心", status: "active", icon: "📋" },
  { to: "/research", label: "文献研究", status: "demo", icon: "📚" },
  { to: "/translate", label: "翻译润色", status: "coming", icon: "🌐" },
  { to: "/admin", label: "系统管理", status: "active", icon: "⚙️" },
];

const statusDot: Record<string, string> = {
  active: "bg-green-500",
  demo: "bg-yellow-400",
  coming: "bg-gray-300",
};

const statusLabel: Record<string, string> = {
  active: "",
  demo: "Demo",
  coming: "即将推出",
};

function AppLayout() {
  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 bg-white border-r border-gray-200 flex flex-col shrink-0">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-brand-600 flex items-center justify-center text-white font-bold text-lg">
              S
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 leading-tight">
                ScholarGuard
              </h1>
              <p className="text-xs text-gray-500">学术AI检测平台</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : "text-gray-600"}`
              }
            >
              <span className="text-lg">{item.icon}</span>
              <span className="flex-1">{item.label}</span>
              <span className="flex items-center gap-1.5">
                {statusLabel[item.status] && (
                  <span className="text-[10px] text-gray-400">
                    {statusLabel[item.status]}
                  </span>
                )}
                <span
                  className={`w-2 h-2 rounded-full ${statusDot[item.status]}`}
                />
              </span>
            </NavLink>
          ))}
        </nav>

        {/* User Menu */}
        <div className="px-3 py-3 border-t border-gray-100">
          <UserMenu />
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-100 text-xs text-gray-400">
          <p>ScholarGuard v1.0</p>
          <p className="mt-0.5">Evidence-Based AI Detection</p>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto bg-gray-50">
        <Routes>
          <Route path="/" element={<Navigate to="/detect" replace />} />
          <Route path="/detect" element={<DetectPage />} />
          <Route path="/detect/history" element={<HistoryPage />} />
          <Route path="/suggest" element={<SuggestPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/research" element={<ResearchPage />} />
          <Route path="/translate" element={<TranslatePage />} />
          <Route path="/admin" element={<AdminPage />} />
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
