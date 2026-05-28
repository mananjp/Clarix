import React, { useState } from 'react';
import { Plus, TrendingUp, CheckCircle, FileText, BarChart2, MoreVertical, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
};

const Dashboard = () => {
  const [projects] = useState([
    {
      id: 1,
      name: 'Global Climate Impact Fund 2026',
      type: 'Periodic Annex',
      status: 'Validating',
      progress: 65,
      docs: 3,
      period: '2025-01-01 to 2025-12-31'
    },
    {
      id: 2,
      name: 'Global ESG Equity Portfolio',
      type: 'Entity PAI',
      status: 'Completed',
      progress: 100,
      docs: 8,
      period: '2024-01-01 to 2024-12-31'
    }
  ]);

  return (
    <div className="flex flex-col gap-8 w-full">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Compliance Dashboard</h1>
          <p className="text-slate-500 mt-1 font-medium">Monitor financial product disclosures and entity PAI statements.</p>
        </div>
        <motion.button 
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="btn btn-primary shadow-primary-500/30"
        >
          <Plus size={18} />
          <span>New Project</span>
        </motion.button>
      </div>

      {/* KPI Grid */}
      <motion.div 
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6"
      >
        {[
          { label: 'Active Projects', value: '2', icon: TrendingUp, status: '✦ Live Workspace', color: 'text-primary-600', bg: 'bg-primary-50' },
          { label: 'Completed Reports', value: '1', icon: CheckCircle, status: '✓ Fully Audited', color: 'text-emerald-600', bg: 'bg-emerald-50' },
          { label: 'Ingested Documents', value: '11', icon: FileText, status: '✓ OCR & Chunked', color: 'text-accent-purple', bg: 'bg-purple-50' },
          { label: 'Avg. Audit Progress', value: '82%', icon: BarChart2, status: '✦ Disclosure-ready', color: 'text-blue-600', bg: 'bg-blue-50' },
        ].map((kpi, idx) => (
          <motion.div key={idx} variants={itemVariants} className="glass-card p-6 flex flex-col gap-4 relative overflow-hidden group">
            <div className={`absolute -right-6 -top-6 w-24 h-24 ${kpi.bg} rounded-full blur-2xl opacity-50 group-hover:scale-150 transition-transform duration-500`}></div>
            <div className="flex items-start justify-between relative z-10">
              <span className="text-sm font-semibold text-slate-500">{kpi.label}</span>
              <div className={`w-8 h-8 rounded-lg ${kpi.bg} ${kpi.color} flex items-center justify-center`}>
                <kpi.icon size={18} strokeWidth={2.5} />
              </div>
            </div>
            <div className="relative z-10">
              <span className="text-3xl font-black text-slate-800">{kpi.value}</span>
            </div>
            <div className="mt-auto pt-2 relative z-10">
              <span className={`text-xs font-bold ${kpi.color}`}>{kpi.status}</span>
            </div>
          </motion.div>
        ))}
      </motion.div>

      {/* Projects List */}
      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-bold text-slate-800">Recent Projects</h2>
        
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="grid grid-cols-1 lg:grid-cols-2 gap-6"
        >
          {projects.map(p => (
            <motion.div 
              variants={itemVariants}
              key={p.id} 
              className="glass-card p-6 flex flex-col gap-5 group cursor-pointer"
            >
              <div className="flex justify-between items-start gap-4">
                <div>
                  <h3 className="font-bold text-lg text-slate-800 group-hover:text-primary-600 transition-colors">{p.name}</h3>
                  <p className="text-sm font-medium text-slate-500 mt-1">{p.type}</p>
                </div>
                <button className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors">
                  <MoreVertical size={20} />
                </button>
              </div>
              
              <div className="flex flex-col gap-2">
                <div className="flex justify-between text-xs font-bold text-slate-500">
                  <span>{p.progress}% Completed</span>
                  <span>{p.docs} Documents</span>
                </div>
                <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden shadow-inner">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${p.progress}%` }}
                    transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
                    className={`h-full rounded-full ${p.progress === 100 ? 'bg-emerald-500' : 'bg-primary-500'}`}
                  />
                </div>
              </div>
              
              <div className="flex justify-between items-center mt-2 pt-4 border-t border-slate-100/50">
                <span className="text-xs font-medium text-slate-400">Period: {p.period}</span>
                <span className={`badge ${p.status === 'Completed' ? 'badge-success' : 'badge-warning'}`}>
                  {p.status}
                </span>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </div>
  );
};

export default Dashboard;
