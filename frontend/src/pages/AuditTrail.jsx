import React, { useState, useEffect } from 'react';
import { ArrowLeft, Clock, Activity, Check, Edit3, Shield, Upload, FileText, Loader } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { motion } from 'framer-motion';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const AuditTrail = () => {
  const { projects, isLoadingProjects } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const selectedProject = projects.find(p => p.id === selectedProjectId);
  const [logs, setLogs] = useState([]);
  const [isLogsLoading, setIsLogsLoading] = useState(false);

  // No auto-select, wait for user selection

  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchLogs = async () => {
      setIsLogsLoading(true);
      try {
        const res = await client.get(`/projects/${selectedProjectId}/audit-logs`);
        setLogs(res.data);
      } catch (err) {
        console.error("Failed to fetch audit logs", err);
      } finally {
        setIsLogsLoading(false);
      }
    };
    fetchLogs();
  }, [selectedProjectId]);

  const getIconForAction = (action) => {
    const act = action.toLowerCase();
    if (act.includes('approve')) return <Check size={16} />;
    if (act.includes('draft') || act.includes('revision') || act.includes('edit')) return <Edit3 size={16} />;
    if (act.includes('upload') || act.includes('ingest')) return <Upload size={16} />;
    if (act.includes('process') || act.includes('validate')) return <Shield size={16} />;
    return <Activity size={16} />;
  };

  const getColorForAction = (action) => {
    const act = action.toLowerCase();
    if (act.includes('approve')) return { color: 'text-emerald-500', bg: 'bg-emerald-50', border: 'border-emerald-200' };
    if (act.includes('draft') || act.includes('edit')) return { color: 'text-primary-500', bg: 'bg-primary-50', border: 'border-primary-200' };
    if (act.includes('upload')) return { color: 'text-purple-500', bg: 'bg-purple-50', border: 'border-purple-200' };
    return { color: 'text-slate-500', bg: 'bg-slate-100', border: 'border-slate-200' };
  };

  if (isLoadingProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
        <div className="text-slate-500 font-bold">Loading Audit Trail...</div>
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="flex flex-col gap-6 w-full max-w-4xl mx-auto"
    >
      {/* Top Bar */}
      <div className="glass-card p-6 flex justify-between items-center flex-wrap gap-4">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Active Workspace</span>
              {selectedProject?.status === 'Validating' && (
                <span className="badge badge-warning flex items-center gap-1.5 animate-pulse text-[10px] py-0.5 px-2">
                  <Loader size={10} className="animate-spin" />
                  Validating
                </span>
              )}
            </div>
            {projects.length > 0 ? (
              <select 
                className="mt-1 block w-full bg-transparent text-3xl font-bold text-slate-800 border-none outline-none focus:ring-0 cursor-pointer p-0"
                value={selectedProjectId}
                onChange={(e) => setSelectedProjectId(e.target.value)}
              >
                <option value="" disabled>Select a Project...</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id} className="text-sm">{p.name}</option>
                ))}
              </select>
            ) : (
              <h1 className="text-3xl font-bold text-slate-800 mt-1 tracking-tight">No Projects Found</h1>
            )}
          </div>
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
          {isLogsLoading ? (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-500">
              <div className="w-8 h-8 border-4 border-slate-200 border-t-primary-600 rounded-full animate-spin"></div>
              <span className="font-bold text-sm">Fetching immutable logs...</span>
            </div>
          ) : !selectedProjectId ? (
            <div className="p-12 text-center text-slate-500 font-medium glass-card">
              Please select a project from the Active Workspace dropdown above.
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-slate-500 font-medium">No audit logs found for this project.</div>
          ) : (
            logs.map((log) => {
              const styles = getColorForAction(log.action);
              return (
                <motion.div 
                  variants={{
                    hidden: { opacity: 0, x: -20 },
                    show: { opacity: 1, x: 0 }
                  }}
                  key={log.id} 
                  className="relative pl-8 group"
                >
                  {/* Timeline dot */}
                  <motion.div 
                    whileHover={{ scale: 1.2, rotate: 5 }}
                    className={`absolute -left-10 w-8 h-8 rounded-full flex items-center justify-center text-sm shadow-md border-2 border-white z-10 ${styles.bg} ${styles.color}`} 
                  >
                    {getIconForAction(log.action)}
                  </motion.div>
                  
                  <div className="bg-white/60 backdrop-blur-sm border border-slate-100 p-5 rounded-2xl shadow-sm hover:shadow-md transition-shadow">
                    <div className="flex flex-col gap-2">
                      <div className="flex justify-between items-center flex-wrap gap-2">
                        <span className="font-bold text-slate-800">{log.actor_username ? `${log.actor_username} (${log.actor_role})` : 'System'}</span>
                        <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5 bg-slate-100 px-2.5 py-1 rounded-full">
                          <Clock size={12} /> {new Date(log.created_at).toLocaleString()}
                        </span>
                      </div>
                      <div className="text-sm text-slate-600 mt-1 flex items-center flex-wrap gap-2">
                        <strong className="text-slate-800 bg-slate-100 px-2 py-0.5 rounded text-xs tracking-wider uppercase">{log.action}</strong>
                        <span>mapped to</span>
                        <code className={`px-2.5 py-1 rounded-md text-xs font-bold font-mono border ${styles.bg} ${styles.border} ${styles.color}`}>
                          {log.entity_type}: {log.entity_id}
                        </code>
                      </div>
                    </div>
                  </div>
                </motion.div>
              );
            })
          )}
        </motion.div>
      </div>
    </motion.div>
  );
};

export default AuditTrail;
