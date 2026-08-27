function StatCard({ label, value, icon: Icon, trend, accentColor }) {
  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl p-5 border border-slate-200 dark:border-slate-700 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-500 dark:text-slate-400 font-medium">{label}</p>
          <p className="text-3xl font-bold text-slate-900 dark:text-white mt-1">{value}</p>
          {trend && <p className="text-xs text-slate-400 mt-1">{trend}</p>}
        </div>
        <div className={'w-10 h-10 rounded-lg flex items-center justify-center ' + accentColor}>
          <Icon size={20} className="text-white" />
        </div>
      </div>
    </div>
  )
}

export default StatCard
