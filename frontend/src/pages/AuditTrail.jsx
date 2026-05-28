import React from 'react';
import { ArrowLeft, Clock, Activity } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';

const AuditTrail = () => {
  const timeline = [
    {
      id: 1,
      action: 'APPROVE',
      actor: 'jane_doe (Reviewer)',
      date: '5/28/2026, 11:30:00 AM',
      entity: 'PAI_GHG_SCOPE1',
      icon: '✓',
      color: 'text-emerald-500',
      bg: 'bg-emerald-50',
      border: 'border-emerald-200'
    },
    {
      id: 2,
      action: 'MANUAL REVISION SAVED',
      actor: 'jane_doe (Reviewer)',
      date: '5/28/2026, 11:28:45 AM',
      entity: 'PAI_GHG_SCOPE1',
      icon: '✏️',
      color: 'text-primary-500',
      bg: 'bg-primary-50',
      border: 'border-primary-200'
    },
    {
      id: 3,
      action: 'VALIDATE',
      actor: 'System Processes',
      date: '5/28/2026, 10:15:00 AM',
      entity: 'ALL_FIELDS',
      icon: '🛡️',
      color: 'text-slate-500',
      bg: 'bg-slate-100',
      border: 'border-slate-200'
    },
    {
      id: 4,
      action: 'UPLOAD',
      actor: 'admin (Administrator)',
      date: '5/28/2026, 10:00:00 AM',
      entity: '2025_Annual_Sustainability_Report.pdf',
      icon: '📥',
      color: 'text-slate-500',
      bg: 'bg-slate-100',
      border: 'border-slate-200'
    }
  ];

  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="flex flex-col gap-6 w-full max-w-4xl mx-auto"
    >
      {/* Top Bar */}
      <div className="glass-card p-6 flex justify-between items-center flex-wrap gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Audit Logs & Traceability</span>
          <h1 className="text-3xl font-bold text-slate-800 mt-1 tracking-tight">Project Audit Trail</h1>
        </div>
        <NavLink to="/matrix" className="btn btn-secondary border-none shadow-none bg-slate-100/50 hover:bg-slate-200/50">
          <ArrowLeft size={16} />
          <span className="font-semibold">Back to Matrix</span>
        </NavLink>
      </div>

      <div className="glass-card p-8 flex flex-col gap-8 min-h-[450px]">
        <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center text-slate-600 shadow-sm border border-white">
            <Activity size={20} />
          </div>
          <div>
            <h3 className="font-bold text-xl text-slate-800">Compliance History Timeline</h3>
            <p className="text-sm font-medium text-slate-500 mt-1">Immutable log of all project updates and compliance scans.</p>
          </div>
        </div>

        <motion.div 
          initial="hidden" animate="show"
          variants={{
            hidden: { opacity: 0 },
            show: { opacity: 1, transition: { staggerChildren: 0.15 } }
          }}
          className="flex flex-col gap-8 pl-4 border-l-2 border-slate-200 relative ml-4"
        >
          {timeline.map((item, index) => (
            <motion.div 
              variants={{
                hidden: { opacity: 0, x: -20 },
                show: { opacity: 1, x: 0 }
              }}
              key={item.id} 
              className="relative pl-8 group"
            >
              {/* Timeline dot */}
              <motion.div 
                whileHover={{ scale: 1.2, rotate: 5 }}
                className={`absolute -left-10 w-8 h-8 rounded-full flex items-center justify-center text-sm shadow-md border-2 border-white z-10 ${item.bg} ${item.color}`} 
              >
                {item.icon}
              </motion.div>
              
              <div className="bg-white/60 backdrop-blur-sm border border-slate-100 p-5 rounded-2xl shadow-sm hover:shadow-md transition-shadow">
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between items-center flex-wrap gap-2">
                    <span className="font-bold text-slate-800">{item.actor}</span>
                    <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5 bg-slate-100 px-2.5 py-1 rounded-full">
                      <Clock size={12} /> {item.date}
                    </span>
                  </div>
                  <div className="text-sm text-slate-600 mt-1 flex items-center flex-wrap gap-2">
                    <strong className="text-slate-800 bg-slate-100 px-2 py-0.5 rounded text-xs tracking-wider">{item.action}</strong>
                    <span>mapped to</span>
                    <code className={`px-2.5 py-1 rounded-md text-xs font-bold font-mono border ${item.bg} ${item.border} ${item.color}`}>
                      {item.entity}
                    </code>
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </motion.div>
  );
};

export default AuditTrail;
