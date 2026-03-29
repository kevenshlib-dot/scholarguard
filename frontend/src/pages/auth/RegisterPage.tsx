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
      return { level: 1, label: "太短", color: "bg-red-500" };
    if (password.length < 8)
      return { level: 2, label: "一般", color: "bg-yellow-500" };
    const hasUpper = /[A-Z]/.test(password);
    const hasLower = /[a-z]/.test(password);
    const hasDigit = /\d/.test(password);
    const hasSpecial = /[^A-Za-z0-9]/.test(password);
    const variety = [hasUpper, hasLower, hasDigit, hasSpecial].filter(
      Boolean
    ).length;
    if (variety >= 3 && password.length >= 10)
      return { level: 4, label: "强", color: "bg-green-500" };
    if (variety >= 2)
      return { level: 3, label: "中等", color: "bg-blue-500" };
    return { level: 2, label: "一般", color: "bg-yellow-500" };
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4 py-8">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-xl bg-brand-600 text-white font-bold text-2xl mb-4">
            S
          </div>
          <h1 className="text-2xl font-bold text-gray-900">ScholarGuard</h1>
          <p className="text-sm text-gray-500 mt-1">学术AI检测平台</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-xl font-semibold text-gray-900 mb-6">注册</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm mb-4">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                用户名
              </label>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                邮箱
              </label>
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
              <label className="block text-sm font-medium text-gray-700 mb-1">
                密码
              </label>
              <input
                type="password"
                className="input"
                placeholder="至少6个字符"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                required
              />
              {/* Password strength indicator */}
              {password.length > 0 && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-colors ${
                          i <= passwordStrength.level
                            ? passwordStrength.color
                            : "bg-gray-200"
                        }`}
                      />
                    ))}
                  </div>
                  <p
                    className={`text-xs mt-1 ${
                      passwordTooShort
                        ? "text-red-500"
                        : "text-gray-500"
                    }`}
                  >
                    密码强度：{passwordStrength.label}
                    {passwordTooShort && "（至少需要6个字符）"}
                  </p>
                </div>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                确认密码
              </label>
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
                <p className="text-xs text-red-500 mt-1">两次密码输入不一致</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                机构名称
                <span className="text-gray-400 font-normal ml-1">（选填）</span>
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
              className="btn-primary w-full justify-center"
              disabled={loading || !canSubmit}
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg
                    className="animate-spin h-4 w-4 text-white"
                    viewBox="0 0 24 24"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="none"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                  注册中...
                </span>
              ) : (
                "注册"
              )}
            </button>
          </form>

          <p className="text-center text-sm text-gray-500 mt-6">
            已有账号？
            <Link
              to="/login"
              className="text-brand-600 hover:text-brand-700 font-medium ml-1"
            >
              立即登录
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
