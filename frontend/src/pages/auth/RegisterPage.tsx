import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [orgName, setOrgName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const passwordTooShort = password.length > 0 && password.length < 6;
  const passwordMismatch =
    confirmPassword.length > 0 && password !== confirmPassword;

  const passwordStrength = (() => {
    if (password.length === 0) return { level: 0, label: "", color: "" };
    if (password.length < 6)
      return { level: 1, label: "太短", color: "bg-red-400" };
    if (password.length < 8)
      return { level: 2, label: "一般", color: "bg-amber-400" };
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasDigit = /\d/.test(password);
    const hasSpecial = /[^A-Za-z0-9]/.test(password);
    const variety = [hasUpper, hasLower, hasDigit, hasSpecial].filter(
      Boolean
    ).length;
    if (variety >= 3 && password.length >= 10)
      return { level: 4, label: "强", color: "bg-emerald-400" };
    if (variety >= 2)
      return { level: 3, label: "中等", color: "bg-blue-400" };
    return { level: 2, label: "一般", color: "bg-amber-400" };
  })();

  const canSubmit =
    username.trim() !== "" &&
    email.trim() !== "" &&
    password.length >= 6 &&
    password === confirmPassword;

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError("");
    setLoading(true);
    try {
      await register(
        username,
        email,
        password,
        orgName.trim() || undefined
      );
      navigate("/detect", { replace: true });
    } catch (err: unknown) {
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { data?: { detail?: string } } }).response?.data
          ?.detail
      ) {
        setError(
          (err as { response: { data: { detail: string } } }).response.data
            .detail
        );
      } else {
        setError("注册失败，请稍后重试");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-brand-50/30 to-slate-100 px-4 py-8">
      {/* Decorative blobs */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-brand-200/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-brand-300/15 rounded-full blur-3xl" />
      </div>

      <div className="w-full max-w-[420px] relative">
        {/* Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-600 to-brand-400 text-white font-bold text-2xl mb-5 shadow-xl shadow-brand-500/30">
            S
          </div>
          <h1 className="text-2xl font-bold text-gray-900 tracking-tight">
            ScholarGuard
          </h1>
          <p className="text-sm text-gray-400 mt-1">学术 AI 检测平台</p>
        </div>

        {/* Card */}
        <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl shadow-gray-200/50 border border-white/60 p-8">
          <h2 className="text-lg font-bold text-gray-900 mb-6">
            创建账号
          </h2>

          {error && (
            <div className="bg-red-50 border border-red-100 text-red-600 px-4 py-3 rounded-xl text-sm mb-5 flex items-center gap-2">
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">用户名</label>
              <input
                type="text"
                className="input"
                placeholder="输入用户名"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="username"
                required
              />
            </div>

            <div>
              <label className="label">邮箱</label>
              <input
                type="email"
                className="input"
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>

            <div>
              <label className="label">密码</label>
              <input
                type="password"
                className="input"
                placeholder="至少6个字符"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              {password.length > 0 && (
                <div className="mt-2.5">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                          i <= passwordStrength.level
                            ? passwordStrength.color
                            : "bg-gray-200"
                        }`}
                      />
                    ))}
                  </div>
                  <p
                    className={`text-xs mt-1.5 font-medium ${
                      passwordTooShort ? "text-red-500" : "text-gray-400"
                    }`}
                  >
                    密码强度：{passwordStrength.label}
                    {passwordTooShort && "（至少需要6个字符）"}
                  </p>
                </div>
              )}
            </div>

            <div>
              <label className="label">确认密码</label>
              <input
                type="password"
                className="input"
                placeholder="再次输入密码"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              {passwordMismatch && (
                <p className="text-xs text-red-500 mt-1.5 font-medium">
                  两次密码输入不一致
                </p>
              )}
            </div>

            <div>
              <label className="label">
                机构名称
                <span className="text-gray-300 font-normal ml-1 normal-case tracking-normal">（选填）</span>
              </label>
              <input
                type="text"
                className="input"
                placeholder="所属学校或机构"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full justify-center py-3 mt-2"
              disabled={loading || !canSubmit}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  注册中...
                </span>
              ) : (
                "注册"
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-400 mt-6">
            已有账号？
            <Link
              to="/login"
              className="text-brand-600 hover:text-brand-700 font-semibold ml-1"
            >
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
