export default function TranslatePage() {
  return (
    <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
      {/* Page header */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 tracking-tight">翻译润色</h2>
        <p className="text-[13px] text-gray-400 mt-1">学术翻译与润色功能</p>
      </div>

      {/* Coming soon card */}
      <div className="card rounded-2xl flex flex-col items-center justify-center py-20 text-center">
        <div className="w-14 h-14 rounded-xl bg-gray-100 flex items-center justify-center mb-5">
          <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 21l5.25-11.25L21 21m-9-3h7.5M3 5.621a48.474 48.474 0 016-.371m0 0c1.12 0 2.233.038 3.334.114M9 5.25V3m3.334 2.364C13.18 5.697 14.024 6 14.924 6c1.08 0 2.1-.278 2.99-.764M9 5.25c-2.676 0-5.216.584-7.499 1.632" />
          </svg>
        </div>
        <p className="text-sm font-medium text-gray-700 mb-1">功能开发中</p>
        <p className="text-[13px] text-gray-400 mb-6 max-w-sm leading-relaxed">
          学术翻译与润色功能正在开发中，即将推出。该功能将支持中英互译、学术表达润色以及领域术语对齐。
        </p>
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-50 border border-gray-200 text-xs text-gray-400">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-300" />
          即将推出
        </div>

        <div className="mt-14 grid grid-cols-3 gap-8 text-center max-w-md w-full">
          {[
            {
              title: "中英互译",
              desc: "高质量学术翻译",
              icon: (
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
                </svg>
              ),
            },
            {
              title: "表达润色",
              desc: "优化学术表达",
              icon: (
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125" />
                </svg>
              ),
            },
            {
              title: "术语对齐",
              desc: "领域专业术语",
              icon: (
                <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
                </svg>
              ),
            },
          ].map((f) => (
            <div key={f.title} className="flex flex-col items-center gap-2">
              <div className="w-10 h-10 rounded-lg bg-gray-50 border border-gray-100 flex items-center justify-center">
                {f.icon}
              </div>
              <p className="text-sm font-medium text-gray-700">{f.title}</p>
              <p className="text-xs text-gray-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
