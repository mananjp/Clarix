import React, { useState, useEffect } from 'react';
import { FileText, CheckCircle, XCircle, AlertTriangle, Edit3, MessageSquare, ExternalLink, Loader, ChevronRight, Hash, Shield, CornerDownRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import client from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useProjects } from '../context/ProjectContext';

const ReviewerDesk = () => {
  const { currentUser } = useAuth();
  const { projects = [], isLoadingProjects, selectedProjectId: globalProjectId, selectProject } = useProjects();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedProjectId, setSelectedProjectId] = useState(searchParams.get('projectId') || globalProjectId || '');
  const selectedProject = (projects || []).find(p => String(p.id) === String(selectedProjectId));
  const [matrixItems, setMatrixItems] = useState([]);
  const [isMatrixLoading, setIsMatrixLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [draftText, setDraftText] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  // Sync internal state with global state and URL
  useEffect(() => {
    const urlId = searchParams.get('projectId');
    if (urlId && urlId !== selectedProjectId) {
      setSelectedProjectId(urlId);
      selectProject(urlId);
    } else if (!urlId && globalProjectId && globalProjectId !== selectedProjectId) {
      setSelectedProjectId(globalProjectId);
      setSearchParams({ projectId: globalProjectId }, { replace: true });
    }
  }, [searchParams, globalProjectId]);

  // Single handler — avoids cascade loop between URL and state effects
  const handleProjectSelect = (projectId) => {
    setSelectedProjectId(projectId);
    selectProject(projectId);
    setSelectedItem(null);
    setMatrixItems([]);
    if (projectId) {
      setSearchParams({ projectId }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  // After projects load, validate the URL's projectId exists; clear if stale
  useEffect(() => {
    if (isLoadingProjects || projects.length === 0) return;
    if (selectedProjectId) {
      const exists = projects.some(p => String(p.id) === String(selectedProjectId));
      if (!exists) {
        handleProjectSelect('');
        setMatrixItems([]);
      }
    }
  }, [projects, isLoadingProjects]);

  // Fetch matrix when a valid project is selected
  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchMatrix = async () => {
      setIsMatrixLoading(true);
      try {
        const res = await client.get(`/projects/${selectedProjectId}/matrix`);
        const data = res.data || [];
        setMatrixItems(data);
        if (data.length > 0) {
          setSelectedItem(data[0]);
          setDraftText(data[0].answer_text || '');
        } else {
          setSelectedItem(null);
          setDraftText('');
        }
      } catch (err) {
        console.error("Failed to fetch matrix", err);
        setMatrixItems([]);
        setSelectedItem(null);
      } finally {
        setIsMatrixLoading(false);
      }
    };
    fetchMatrix();
  }, [selectedProjectId]);

  const handleApprove = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.post(`/answers/${selectedItem.answer_id}/approve?reviewer_id=${currentUser.id}`);
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_status: 'Approved' } : i));
      setSelectedItem(prev => ({ ...prev, answer_status: 'Approved' }));
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleReject = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.post(`/answers/${selectedItem.answer_id}/reject?reviewer_id=${currentUser.id}`);
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_status: 'Rejected' } : i));
      setSelectedItem(prev => ({ ...prev, answer_status: 'Rejected' }));
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveDraft = async () => {
    if (!selectedItem?.answer_id) return;
    setIsSaving(true);
    try {
      await client.put(`/answers/${selectedItem.answer_id}`, {
        answer_text: draftText,
        status: 'Draft',
        approved_by_user_id: currentUser.id
      });
      setMatrixItems(prev => prev.map(i => i.field_id === selectedItem.field_id ? { ...i, answer_text: draftText, answer_status: 'Draft' } : i));
      setSelectedItem(prev => ({ ...prev, answer_text: draftText, answer_status: 'Draft' }));
    } catch (err) {
      console.error(err);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoadingProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-4">
        <Loader size={40} className="animate-spin text-primary-600" />
        <span className="text-slate-400 font-black uppercase tracking-widest text-xs">Synchronizing Repository...</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 h-screen max-h-[calc(100vh-6rem)]">
      {/* Header Context */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-6">
        <div>
          <h1 className="text-3xl font-black text-slate-900 tracking-tight uppercase">Clarix Reviewer</h1>
          <p className="text-slate-500 font-bold text-sm mt-1">Audit & refine AI-orchestrated compliance extractions.</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="form-input bg-white min-w-[240px] font-black text-xs uppercase tracking-widest text-slate-700"
            value={selectedProjectId}
            onChange={(e) => handleProjectSelect(e.target.value)}
          >
            <option value="" disabled>Switch Workplace...</option>
            {projects.map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>
      </header>

      {!selectedProjectId ? (
        <div className="flex-1 flex flex-col items-center justify-center glass-card bg-slate-50/50">
          <Shield size={48} className="text-slate-200 mb-4" />
          <p className="text-slate-500 font-bold">Please select a workspace to begin the review cycle.</p>
        </div>
      ) : matrixItems.length === 0 && !isMatrixLoading ? (
        <div className="flex-1 flex flex-col items-center justify-center glass-card bg-slate-50/50">
          <AlertTriangle size={48} className="text-amber-200 mb-4" />
          <p className="text-slate-500 font-bold">No evidence chains found for this project scope.</p>
        </div>
      ) : (
        <div className="flex-1 grid grid-cols-12 gap-6 overflow-hidden min-h-0">
          {/* List Sidebar */}
          <div className="col-span-12 lg:col-span-4 flex flex-col glass-card bg-white p-0 overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-center">
              <span className="text-[11px] font-black text-slate-500 uppercase tracking-widest">Audit Queue ({matrixItems.length})</span>
              <div className="flex gap-2">
                <div className="w-2 h-2 rounded-full bg-emerald-400"></div>
                <div className="w-2 h-2 rounded-full bg-slate-200"></div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto">
              {isMatrixLoading ? (
                <div className="p-12 flex flex-col items-center justify-center gap-3">
                  <Loader size={24} className="animate-spin text-primary-600" />
                  <span className="text-xs font-bold text-slate-400">Loading Matrix...</span>
                </div>
              ) : (
                <div className="divide-y divide-slate-50">
                  {matrixItems.map(item => (
                    <button
                      key={item.field_id}
                      onClick={() => {
                        setSelectedItem(item);
                        setDraftText(item.answer_text || '');
                      }}
                      className={`w-full text-left p-4 transition-all hover:bg-slate-50 flex gap-4 items-start ${selectedItem?.field_id === item.field_id ? 'bg-primary-50/50 border-r-4 border-primary-600' : ''}`}
                    >
                      <div className={`mt-1 p-1.5 rounded-lg ${item.answer_status === 'Approved' ? 'bg-emerald-50 text-emerald-600' : item.answer_status === 'Rejected' ? 'bg-rose-50 text-rose-600' : 'bg-slate-100 text-slate-400'}`}>
                        {item.answer_status === 'Approved' ? <CheckCircle size={14} strokeWidth={3} /> : item.answer_status === 'Rejected' ? <XCircle size={14} strokeWidth={3} /> : <FileText size={14} strokeWidth={3} />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-start gap-2">
                          <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">{item.field_code}</span>
                          {item.mandatory && <span className="text-rose-500 font-bold text-[9px] uppercase tracking-tighter shrink-0">Mandatory</span>}
                        </div>
                        <p className={`text-sm font-bold mt-0.5 truncate ${selectedItem?.field_id === item.field_id ? 'text-primary-700' : 'text-slate-700'}`}>{item.field_label}</p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-[9px] font-black px-1.5 py-0.5 rounded ${item.penalty_tier === 'Critical' ? 'bg-rose-100 text-rose-700' : 'bg-slate-100 text-slate-500'}`}>
                            {item.penalty_tier || 'AUDIT'}
                          </span>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Review Panel */}
          <div className="col-span-12 lg:col-span-8 flex flex-col gap-6 overflow-y-auto">
            <AnimatePresence mode="wait">
              {selectedItem ? (
                <motion.div
                  key={selectedItem.field_id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="flex flex-col gap-6"
                >
                  <div className="glass-card bg-white p-8">
                    <div className="flex justify-between items-start mb-6">
                      <div className="max-w-2xl">
                        <div className="flex items-center gap-2 mb-2">
                          <Hash size={14} className="text-primary-600" />
                          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">{selectedItem.field_code} • {selectedItem.regulation_version}</span>
                        </div>
                        <h2 className="text-2xl font-black text-slate-900 tracking-tight leading-tight uppercase">{selectedItem.field_label}</h2>
                        <div className="flex items-center gap-4 mt-4">
                          <div className="flex items-center gap-2 px-3 py-1 bg-slate-50 rounded-full border border-slate-100">
                            <span className="text-[10px] font-black text-slate-400 uppercase">Framework:</span>
                            <span className="text-[10px] font-black text-slate-700 uppercase tracking-widest">{selectedItem.framework}</span>
                          </div>
                          <div className="flex items-center gap-2 px-3 py-1 bg-slate-50 rounded-full border border-slate-100">
                            <span className="text-[10px] font-black text-slate-400 uppercase">Annex:</span>
                            <span className="text-[10px] font-black text-slate-700 uppercase tracking-widest">{selectedItem.annex_code}</span>
                          </div>
                        </div>
                      </div>
                      <span className={`badge text-xs px-4 py-1.5 ${selectedItem.answer_status === 'Approved' ? 'badge-success' : selectedItem.answer_status === 'Rejected' ? 'badge-danger' : 'badge-default'}`}>
                        {selectedItem.answer_status}
                      </span>
                    </div>

                    <div className="p-5 bg-slate-50/50 rounded-2xl border border-slate-100 mb-8">
                      <h4 className="text-[11px] font-black text-slate-500 uppercase tracking-widest mb-2 flex items-center gap-2">
                        <Shield size={12} />
                        Regulatory Guidance
                      </h4>
                      <p className="text-sm text-slate-600 font-medium leading-relaxed italic">{selectedItem.description || "The extraction must satisfy the detailed RTS criteria for this field."}</p>
                    </div>

                    <div className="space-y-4">
                      <div className="flex justify-between items-center">
                        <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest mb-1 flex items-center gap-2">
                          <Edit3 size={12} />
                          Assessed Disclosure Content
                        </label>
                        <span className="text-[10px] font-bold text-slate-400 italic">Extracted from Project Source Docs</span>
                      </div>
                      <textarea
                        value={draftText}
                        onChange={(e) => setDraftText(e.target.value)}
                        className="form-input min-h-[180px] text-base leading-relaxed bg-slate-50 focus:bg-white transition-all shadow-inner"
                        placeholder="Type evidence-based answer here..."
                      ></textarea>
                      <div className="flex justify-end pt-4 gap-3">
                        <button
                          onClick={handleSaveDraft}
                          disabled={isSaving}
                          className="px-6 py-3 text-sm font-black text-slate-500 hover:text-slate-900 bg-white border border-slate-200 rounded-2xl hover:shadow-lg transition-all disabled:opacity-50"
                        >
                          SAVE AS DRAFT
                        </button>
                        <div className="h-full w-px bg-slate-200 mx-2"></div>
                        <button
                          onClick={handleReject}
                          disabled={isSaving}
                          className="px-6 py-3 text-sm font-black text-rose-600 hover:bg-rose-50 bg-white border border-rose-100 rounded-2xl hover:shadow-lg transition-all disabled:opacity-50 flex items-center gap-2"
                        >
                          <XCircle size={18} />
                          REJECT
                        </button>
                        <button
                          onClick={handleApprove}
                          disabled={isSaving}
                          className="px-8 py-3 text-sm font-black text-white bg-slate-900 border border-slate-900 rounded-2xl hover:bg-slate-800 shadow-xl shadow-slate-900/10 transition-all disabled:opacity-50 flex items-center gap-2"
                        >
                          <CheckCircle size={18} />
                          APPROVE
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Evidence Chain */}
                  <div className="glass-card bg-slate-900 p-8 text-white relative overflow-hidden">
                    <CornerDownRight size={80} className="absolute -top-6 -right-6 text-white/5 rotate-12" />
                    <h4 className="text-[11px] font-black text-white/40 uppercase tracking-widest mb-6 flex items-center gap-2">
                      Active Evidence Chain
                    </h4>

                    <div className="flex flex-col gap-4">
                      {selectedItem.citations && selectedItem.citations.length > 0 ? (
                        selectedItem.citations.map((cite, idx) => (
                          <div key={idx} className="p-4 bg-white/5 border border-white/10 rounded-2xl hover:bg-white/[0.08] transition-all group">
                            <div className="flex justify-between items-start mb-3">
                              <span className="text-[11px] font-black text-primary-400 uppercase tracking-widest flex items-center gap-2">
                                <ExternalLink size={12} />
                                Document Evidence [Ref {idx + 1}]
                              </span>
                              <span className="text-[10px] font-bold text-white/30 uppercase">Conf: {Math.round(cite.confidence_score * 100)}%</span>
                            </div>
                            <p className="text-sm text-white font-medium leading-relaxed">"{cite.citation_text}"</p>
                            <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-3">
                              <span className="text-[10px] font-bold text-white/50">{cite.document_name} • Pg {cite.page_no}</span>
                              <button className="text-[10px] font-black uppercase text-primary-400 hover:text-white transition-colors">View Source Page</button>
                            </div>
                          </div>
                        ))
                      ) : (
                        <div className="p-8 text-center border-2 border-dashed border-white/10 rounded-2xl">
                          <p className="text-white/40 text-xs font-bold uppercase tracking-widest">No evidence links found</p>
                          <p className="text-white/20 text-[10px] mt-1 italic">Run GenAI to extract specific citations</p>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ) : (
                <div className="flex-1 flex flex-col items-center justify-center p-12 text-center">
                  <div className="w-20 h-20 bg-slate-50 rounded-full flex items-center justify-center mb-6">
                    <MessageSquare size={32} className="text-slate-200" />
                  </div>
                  <h3 className="text-xl font-black text-slate-800 tracking-tight uppercase">Audit Queue Ready</h3>
                  <p className="text-slate-400 font-bold max-w-xs mt-2 mx-auto text-sm">Select a compliance requirement from the left to begin evidence verification.</p>
                </div>
              )}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
};

export default ReviewerDesk;
