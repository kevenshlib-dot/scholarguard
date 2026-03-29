export default function TranslatePage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
        <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center mb-6">
          <span className="text-4xl">🌐</span>
        </div>
        <h2 className="text-2xl font-bold text-gray-900 mb-2">翻译润色</h2>
        <p className="text-gray-500 mb-6 max-w-md">
          学术翻译与润色功能正在开发中，即将推出。该功能将支持中英互译、学术表达润色以及领域术语对齐。
        </p>
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-gray-100 text-sm text-gray-500">
          <span className="w-2 h-2 rounded-full bg-gray-300" />
          即将推出
        </div>

        <div className="mt-12 grid grid-cols-3 gap-6 text-center max-w-lg w-full">
          {[
            { icon: "🔄", title: "中英互译", desc: "高质量学术翻译" },
            { icon: "✨", title: "表达润色", desc: "优化学术表达" },
            { icon: "📖", title: "术语对齐", desc: "领域专业术语" },
          ].map((f) => (
            <div key={f.title} className="space-y-2">
              <div className="text-2xl">{f.icon}</div>
              <p className="text-sm font-medium text-gray-700">{f.title}</p>
              <p className="text-xs text-gray-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
