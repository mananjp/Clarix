import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Plus, TrendingUp, CheckCircle, FileText, BarChart2, MoreVertical, X, Sparkles, Check, Trash2, Loader, ArrowRight, ShieldCheck, Briefcase, Edit3 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.1, delayChildren: 0.1 }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 15 },
  show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 30 } }
};

const Dashboard = () => {
  const { projects, isLoadingProjects: loading, fetchProjects, selectedProjectId, selectProject } = useProjects();
  const [showModal, setShowModal] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deletingProjectId, setDeletingProjectId] = useState(null);

  const [projectForm, setProjectForm] = useState({
    name: '',
    disclosure_type: 'periodic',
    reporting_period_start: '2025-01-01',
    reporting_period_end: '2025-12-31'
  });

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      if (editingProject) {
        await client.patch(`/projects/${editingProject.id}`, projectForm);
      } else {
        await client.post('/projects', projectForm);
      }
      setShowModal(false);
      setEditingProject(null);
      setProjectForm({
        name: '',
        disclosure_type: 'periodic',
        reporting_period_start: '2025-01-01',
        reporting_period_end: '2025-12-31'
      });
      fetchProjects();
    } catch (error) {
      console.error("Failed to save project", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditClick = (project, e) => {
    e.stopPropagation();
    setEditingProject(project);
    setProjectForm({
      name: project.name,
      disclosure_type: project.disclosure_type,
      reporting_period_start: project.reporting_period_start,
      reporting_period_end: project.reporting_period_end
    });
    setShowModal(true);
  };

  const handleDeleteProject = async (projectId, e) => {
    e.stopPropagation();
    if (window.confirm("Are you sure you want to delete this project? This cannot be undone.")) {
      setDeletingProjectId(projectId);
      try {
        await client.delete(`/projects/${projectId}`);
        if (selectedProjectId === projectId) selectProject(null);
        await fetchProjects();
      } catch (error) {
        console.error("Failed to delete project", error);
      } finally {
        setDeletingProjectId(null);
      }
    }
  };

  const documentCount = projects.reduce((acc, p) => acc + p.document_count, 0);
  const completedProjects = projects.filter(p => p.status === 'Completed').length;
  const avgProgress = projects.length > 0
    ? Math.round(projects.reduce((acc, p) => acc + p.progress, 0) / projects.length)
    : 0;

  const kpis = [
    { label: 'Active Projects', value: projects.length, icon: Briefcase, bg: 'bg-indigo-50', color: 'text-indigo-600' },
    { label: 'Completed Reports', value: completedProjects, icon: CheckCircle, bg: 'bg-emerald-50', color: 'text-emerald-600' },
    { label: 'Total Documents', value: documentCount, icon: FileText, bg: 'bg-amber-50', color: 'text-amber-600' },
    { label: 'Average Progress', value: `${avgProgress}%`, icon: BarChart2, bg: 'bg-blue-50', color: 'text-blue-600' },
  ];

  return (
    <div className="flex flex-col gap-10 w-full pb-20 font-sans">
      {/* Header */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="text-4xl font-black text-slate-900 tracking-tight">Dashboard</h1>
          <p className="text-slate-500 mt-2 font-semibold">Manage your compliance reporting projects and documents.</p>
        </div>

        <motion.button
          whileTap={{ scale: 0.98 }}
          onClick={() => setShowModal(true)}
          className="px-8 py-4 bg-slate-900 text-white rounded-2xl text-base font-bold shadow-xl shadow-slate-900/10 flex items-center gap-2"
        >
          <Plus size={20} strokeWidth={2.5} />
          <span>New Project</span>
        </motion.button>
      </header>

      {/* KPI Section */}
      <motion.section
        variants={containerVariants}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6"
      >
        {kpis.map((kpi, idx) => (
          <motion.div key={idx} variants={itemVariants} className="bg-white p-8 rounded-[32px] border border-slate-100 shadow-sm shadow-slate-200/50">
            <div className="flex items-center gap-5">
              <div className={`w-14 h-14 rounded-2xl ${kpi.bg} ${kpi.color} flex items-center justify-center shrink-0`}>
                <kpi.icon size={28} strokeWidth={2} />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-400 uppercase tracking-wider">{kpi.label}</p>
                <p className="text-3xl font-black text-slate-900 mt-0.5">{kpi.value}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </motion.section>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-8 space-y-6">
          <div className="flex justify-between items-center px-2">
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Active Projects</h2>
            <div className="text-sm font-bold text-slate-400 uppercase tracking-widest">{projects.length} Total</div>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-32 bg-white rounded-[32px] border border-slate-100">
              <Loader size={32} className="animate-spin text-slate-200 mb-4" />
              <span className="text-slate-400 font-bold">Loading projects...</span>
            </div>
          ) : projects.length === 0 ? (
            <div className="text-center py-32 px-8 bg-white border-2 border-dashed border-slate-100 rounded-[32px]">
              <Sparkles size={48} className="mx-auto text-slate-200 mb-6" />
              <h3 className="text-xl font-bold text-slate-900 mb-2">Ready to start?</h3>
              <p className="text-slate-500 max-w-xs mx-auto mb-10 leading-relaxed">
                Create your first project to start tracking your compliance documents and reporting progress.
              </p>
              <button
                onClick={() => setShowModal(true)}
                className="px-8 py-4 bg-slate-900 text-white rounded-2xl text-base font-bold shadow-lg shadow-slate-900/10"
              >
                Create First Project
              </button>
            </div>
          ) : (
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="show"
              className="space-y-4"
            >
              {projects.map(p => (
                <motion.div
                  variants={itemVariants}
                  key={p.id}
                  onClick={() => {
                    selectProject(p.id);
                    window.location.href = `/matrix?projectId=${p.id}`;
                  }}
                  className={`bg-white border border-slate-100 p-8 rounded-[32px] hover:border-slate-300 transition-all cursor-pointer flex flex-col md:flex-row justify-between items-start md:items-center gap-8 ${selectedProjectId === p.id ? 'ring-2 ring-slate-900 ring-offset-2' : 'shadow-sm shadow-slate-200/50'}`}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-4 mb-3">
                      <h3 className="text-2xl font-bold text-slate-900 tracking-tight">
                        {p.name}
                      </h3>
                      <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider ${p.status === 'Completed' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-50 text-slate-500'}`}>
                        {p.status}
                      </span>
                    </div>

                    <div className="flex items-center gap-6 text-sm font-bold text-slate-400">
                      <div className="flex items-center gap-2">
                        <FileText size={16} /> {p.document_count} Documents
                      </div>
                      <div className="w-1 h-1 bg-slate-200 rounded-full"></div>
                      <div className="uppercase tracking-widest text-xs">{p.disclosure_type}</div>
                    </div>
                  </div>

                  <div className="w-full md:w-56">
                    <div className="flex justify-between items-end mb-2 px-1">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Progress</span>
                      <span className="text-base font-black text-slate-900">{p.progress}%</span>
                    </div>
                    <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${p.progress}%` }}
                        transition={{ duration: 1, ease: "easeOut" }}
                        className={`h-full ${p.progress === 100 ? 'bg-emerald-500' : 'bg-slate-900'}`}
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      onClick={(e) => handleEditClick(p, e)}
                      className="p-3 bg-slate-50 text-slate-400 hover:text-slate-900 hover:bg-slate-100 transition-all rounded-xl"
                    >
                      <Edit3 size={18} />
                    </button>
                    <button
                      onClick={(e) => handleDeleteProject(p.id, e)}
                      className="p-3 bg-slate-50 text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all rounded-xl"
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </motion.div>
              ))}
            </motion.div>
          )}
        </div>

        <div className="lg:col-span-4 space-y-6">
          <div className="bg-slate-900 p-10 rounded-[32px] text-white shadow-2xl shadow-slate-900/20">
            <h3 className="text-xl font-bold mb-4">Need help?</h3>
            <p className="text-slate-400 font-medium leading-relaxed mb-8">
              Explore our comprehensive guide on how to manage compliance disclosures and regulatory reporting.
            </p>
            <button className="w-full py-4 bg-white text-slate-900 rounded-2xl font-bold hover:bg-slate-50 transition-all shadow-lg">
              Open Documentation
            </button>
          </div>

          <div className="bg-white border border-slate-100 rounded-[32px] overflow-hidden shadow-sm shadow-slate-200/50">
            <div className="p-8 border-b border-slate-50">
              <h3 className="text-sm font-black text-slate-900 uppercase tracking-widest">System Health</h3>
            </div>
            <div className="p-8 space-y-6">
              {[
                { name: 'Analysis Engine', status: 'Healthy', color: 'bg-emerald-500' },
                { name: 'Document Ingestion', status: 'Ready', color: 'bg-emerald-500' },
                { name: 'Database Connector', status: 'Active', color: 'bg-indigo-500' },
              ].map((s, i) => (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-sm font-bold text-slate-600">{s.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">{s.status}</span>
                    <div className={`w-2 h-2 rounded-full ${s.color} animate-pulse`}></div>
                  </div>
                </div>
              ))}
            </div>
            <div className="px-8 py-6 bg-slate-50 text-center">
              <span className="text-[10px] font-bold text-slate-300 uppercase tracking-[0.3em]">All systems operational</span>
            </div>
          </div>
        </div>
      </div>

      {/* Simplified Project Modal */}
      {createPortal(
        <AnimatePresence>
          {showModal && (
            <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 bg-slate-950/20 backdrop-blur-md">
              <motion.div
                initial={{ opacity: 0, scale: 0.98, y: 20 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, y: 20 }}
                className="bg-white rounded-[40px] p-12 w-full max-w-xl shadow-2xl shadow-slate-950/10"
              >
                <div className="flex justify-between items-start mb-10">
                  <div>
                    <h3 className="text-3xl font-black text-slate-900 tracking-tight">
                      {editingProject ? 'Edit Project' : 'New Project'}
                    </h3>
                    <p className="text-slate-500 font-medium mt-2">
                      {editingProject ? 'Update your project settings.' : 'Set up a new reporting workspace.'}
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setShowModal(false);
                      setEditingProject(null);
                    }}
                    className="p-3 text-slate-400 hover:text-slate-900 hover:bg-slate-50 rounded-2xl transition-all"
                  >
                    <X size={24} />
                  </button>
                </div>

                <form onSubmit={handleCreateProject} className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Project Name</label>
                    <input
                      type="text"
                      required
                      value={projectForm.name}
                      onChange={(e) => setProjectForm({ ...projectForm, name: e.target.value })}
                      className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-[24px] text-base text-slate-900 placeholder:text-slate-300 focus:outline-none focus:border-slate-900 focus:bg-white transition-all shadow-sm"
                      placeholder="e.g. 2025 Sustainability Report"
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-bold text-slate-700 ml-1">Reporting Framework</label>
                    <select
                      value={projectForm.disclosure_type}
                      onChange={(e) => setProjectForm({ ...projectForm, disclosure_type: e.target.value })}
                      className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-[24px] text-base text-slate-900 focus:outline-none focus:border-slate-900 focus:bg-white transition-all shadow-sm appearance-none"
                      disabled={!!editingProject}
                    >
                      <option value="periodic">SFDR Periodic Annex</option>
                      <option value="precontractual">SFDR Pre-Contractual</option>
                      <option value="entity_pai">BRSR / Entity PAI</option>
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-700 ml-1">Start Date</label>
                      <input
                        type="date"
                        required
                        value={projectForm.reporting_period_start}
                        onChange={(e) => setProjectForm({ ...projectForm, reporting_period_start: e.target.value })}
                        className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-[24px] text-sm"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-bold text-slate-700 ml-1">End Date</label>
                      <input
                        type="date"
                        required
                        value={projectForm.reporting_period_end}
                        onChange={(e) => setProjectForm({ ...projectForm, reporting_period_end: e.target.value })}
                        className="w-full px-6 py-4 bg-slate-50 border border-slate-200 rounded-[24px] text-sm"
                      />
                    </div>
                  </div>

                  <div className="flex gap-4 pt-10">
                    <button
                      type="button"
                      onClick={() => {
                        setShowModal(false);
                        setEditingProject(null);
                      }}
                      className="flex-1 py-5 text-sm font-bold text-slate-400 hover:text-slate-900 transition-all"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="flex-[2] py-5 bg-slate-900 text-white rounded-[24px] text-base font-bold shadow-xl shadow-slate-900/10 disabled:opacity-50"
                    >
                      {isSubmitting ? 'Saving...' : (editingProject ? 'Save Changes' : 'Create Project')}
                    </button>
                  </div>
                </form>
              </motion.div>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&display=swap');
        body { font-family: 'Outfit', sans-serif; }
      `}</style>
    </div>
  );
};

export default Dashboard;
