import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Plus, TrendingUp, CheckCircle, FileText, BarChart2, MoreVertical, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import client from '../api/client';

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
  const [projects, setProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // New Project Form State
  const [newProject, setNewProject] = useState({
    name: '',
    disclosure_type: 'Periodic Annex',
    reporting_period_start: '2025-01-01',
    reporting_period_end: '2025-12-31'
  });

  const fetchProjects = async () => {
    try {
      const response = await client.get('/projects');
      setProjects(response.data);
    } catch (error) {
      console.error("Failed to load projects", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await client.post('/projects', newProject);
      setShowModal(false);
      setNewProject({
        name: '',
        disclosure_type: 'Periodic Annex',
        reporting_period_start: '2025-01-01',
        reporting_period_end: '2025-12-31'
      });
      fetchProjects(); // Refresh the list
    } catch (error) {
      console.error("Failed to create project", error);
      alert("Failed to create project.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const documentCount = projects.reduce((acc, p) => acc + p.document_count, 0);
  const completedProjects = projects.filter(p => p.status === 'Completed').length;
  const avgProgress = projects.length > 0 
    ? Math.round(projects.reduce((acc, p) => acc + p.progress, 0) / projects.length)
    : 0;

  const kpis = [
    { label: 'Active Projects', value: projects.length.toString(), icon: TrendingUp, status: '✦ Live Workspace', color: 'text-primary-600', bg: 'bg-primary-50' },
    { label: 'Completed Reports', value: completedProjects.toString(), icon: CheckCircle, status: '✓ Fully Audited', color: 'text-emerald-600', bg: 'bg-emerald-50' },
    { label: 'Ingested Documents', value: documentCount.toString(), icon: FileText, status: '✓ OCR & Chunked', color: 'text-accent-purple', bg: 'bg-purple-50' },
    { label: 'Avg. Audit Progress', value: `${avgProgress}%`, icon: BarChart2, status: '✦ Disclosure-ready', color: 'text-blue-600', bg: 'bg-blue-50' },
  ];

  return (
    <div className="flex flex-col gap-8 w-full relative">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-slate-900 tracking-tight">Compliance Dashboard</h1>
          <p className="text-slate-500 mt-1 font-medium">Monitor financial product disclosures and entity PAI statements.</p>
        </div>
        <motion.button 
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => setShowModal(true)}
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
        {kpis.map((kpi, idx) => (
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
        
        {loading ? (
          <div className="text-center py-12 text-slate-500 font-medium">Loading projects...</div>
        ) : projects.length === 0 ? (
          <div className="text-center py-12 text-slate-500 font-medium glass-card">No projects found. Click "New Project" to start.</div>
        ) : (
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
                    <p className="text-sm font-medium text-slate-500 mt-1">{p.disclosure_type}</p>
                  </div>
                  <button className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-100 transition-colors">
                    <MoreVertical size={20} />
                  </button>
                </div>
                
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between text-xs font-bold text-slate-500">
                    <span>{p.progress}% Completed</span>
                    <span>{p.document_count} Documents</span>
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
                  <span className="text-xs font-medium text-slate-400">Period: {p.reporting_period_start} to {p.reporting_period_end}</span>
                  <span className={`badge ${p.status === 'Completed' ? 'badge-success' : p.status === 'Validating' ? 'badge-warning' : 'bg-indigo-50 text-indigo-700'}`}>
                    {p.status}
                  </span>
                </div>
              </motion.div>
            ))}
          </motion.div>
        )}
      </div>

      {/* New Project Modal */}
      {createPortal(
        <AnimatePresence>
          {showModal && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-md"
            >
              <motion.div 
                initial={{ scale: 0.95, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 20 }}
                className="glass-card rounded-3xl p-8 w-full max-w-md shadow-2xl relative overflow-hidden"
              >
                {/* Decorative blob */}
                <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary-400 rounded-full blur-[80px] opacity-20 pointer-events-none"></div>

                <div className="flex justify-between items-start mb-8 relative z-10">
                  <div>
                    <h3 className="text-2xl font-extrabold text-slate-900 tracking-tight">New Project</h3>
                    <p className="text-slate-500 font-medium text-sm mt-1">Configure your reporting workspace</p>
                  </div>
                  <button 
                    onClick={() => setShowModal(false)}
                    className="text-slate-400 hover:text-slate-800 transition-colors p-2 rounded-xl hover:bg-slate-100 bg-white shadow-sm border border-slate-100"
                  >
                    <X size={20} />
                  </button>
                </div>

                <form onSubmit={handleCreateProject} className="flex flex-col gap-5 relative z-10">
                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-1.5">Project Name</label>
                    <input
                      type="text"
                      required
                      value={newProject.name}
                      onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                      className="form-input py-3 text-base"
                      placeholder="e.g. Global Equity Fund 2026"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-slate-700 mb-1.5">Disclosure Type</label>
                    <select
                      value={newProject.disclosure_type}
                      onChange={(e) => setNewProject({ ...newProject, disclosure_type: e.target.value })}
                      className="form-input py-3 text-base"
                    >
                      <option value="Periodic Annex">Periodic Annex</option>
                      <option value="Precontractual">Precontractual</option>
                      <option value="Entity PAI">Entity PAI</option>
                    </select>
                  </div>

                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-bold text-slate-700 mb-1.5">Start Date</label>
                      <input
                        type="date"
                        required
                        value={newProject.reporting_period_start}
                        onChange={(e) => setNewProject({ ...newProject, reporting_period_start: e.target.value })}
                        className="form-input py-3 text-sm"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-bold text-slate-700 mb-1.5">End Date</label>
                      <input
                        type="date"
                        required
                        value={newProject.reporting_period_end}
                        onChange={(e) => setNewProject({ ...newProject, reporting_period_end: e.target.value })}
                        className="form-input py-3 text-sm"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end gap-3 mt-6">
                    <button
                      type="button"
                      onClick={() => setShowModal(false)}
                      className="px-5 py-3 text-sm font-bold text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="btn btn-primary px-6 py-3 shadow-primary-500/30 disabled:opacity-70"
                    >
                      {isSubmitting ? (
                        <span className="flex items-center gap-2">
                          <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                          </svg>
                          Creating...
                        </span>
                      ) : (
                        <span className="font-bold">Create Workspace</span>
                      )}
                    </button>
                  </div>
                </form>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
};

export default Dashboard;
