import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, Loader, FileText, CheckCircle, XCircle, Play, Download, Package, ArrowRight, ClipboardCheck, ShieldCheck, BarChart3 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';
import { useAuth } from '../context/AuthContext';

/**
 * SFDR Asset-Manager Core Loop.
 *
 * A single guided workflow for an asset manager completing SFDR Principal
 * Adverse-Impact (PAI) reporting:
 *   Step 1  Upload investee sustainability reports / allocation documents
 *   Step 2  Generate PAI answers + evidence (GenAI / rules engine)
 *   Step 3  Review & approve each PAI indicator
 *   Step 4  Export the filing package (markdown / XBRL / audit zip)
 *
 * The ESG-feed coverage view (investee PAI data availability) is available on
 * the dedicated /esg-feed page.
 */
const SfdrCoreLoop = () => {
  const { currentUser } = useAuth();
  const { projects = [], isLoadingProjects, selectedProjectId: globalProjectId, selectProject } = useProjects();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedProjectId, setSelectedProjectId] = useState(searchParams.get('projectId') || globalProjectId || '');

  const [step, setStep] = useState(1);
  const [documents, setDocuments] = useState([]);
  const [matrixItems, setMatrixItems] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState('');
  const fileInputRef = useRef(null);

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

  const handleProjectSelect = (projectId) => {
    setSelectedProjectId(projectId);
    selectProject(projectId);
    if (projectId) {
      setSearchParams({ projectId }, { replace: true });
    } else {
      setSearchParams({}, { replace: true });
    }
  };

  useEffect(() => {
    if (isLoadingProjects || projects.length === 0) return;
    if (selectedProjectId) {
      const exists = projects.some(p => String(p.id) === String(selectedProjectId));
      if (!exists) handleProjectSelect('');
    }
  }, [projects, isLoadingProjects]);

  const fetchData = async () => {
    if (!selectedProjectId) return;
    try {
      const [matrixRes, docsRes] = await Promise.all([
        client.get(`/projects/${selectedProjectId}/matrix`),
        client.get(`/projects/${selectedProjectId}/documents`),
      ]);
      setMatrixItems(matrixRes.data || []);
      setDocuments(docsRes.data || []);
    } catch (err) {
      console.error('Failed to fetch data', err);
    }
  };

  useEffect(() => {
    if (selectedProjectId) fetchData();
  }, [selectedProjectId]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedProjectId) return;
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', 'sustainability_report');
    try {
      await client.post(`/projects/${selectedProjectId}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      await fetchData();
    } catch (err) {
      console.error('Upload failed', err);
      alert('Failed to upload document: ' + (err.response?.data?.detail || 'unknown error'));
    } finally {
      setIsUploading(false);
      e.target.value = null;
    }
  };

  const handleGenerate = async () => {
    if (!selectedProjectId) return;
    setIsProcessing(true);
    try {
      await client.post(`/projects/${selectedProjectId}/process`);
      await fetchData();
      setStep(3);
    } catch (err) {
      console.error('GenAI processing failed', err);
      alert('Failed to generate answers: ' + (err.response?.data?.detail || 'upload documents first'));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleApprove = async (item) => {
    if (!item.answer_id) return;
    try {
      await client.post(`/answers/${item.answer_id}/approve?reviewer_id=${currentUser.id}`);
      setMatrixItems(prev => prev.map(i => i.field_id === item.field_id ? { ...i, answer_status: 'Approved' } : i));
    } catch (err) {
      console.error(err);
    }
  };

  const handleReject = async (item) => {
    if (!item.answer_id) return;
    try {
      await client.post(`/answers/${item.answer_id}/reject?reviewer_id=${currentUser.id}`);
      setMatrixItems(prev => prev.map(i => i.field_id === item.field_id ? { ...i, answer_status: 'Rejected' } : i));
    } catch (err) {
      console.error(err);
    }
  };

  const handleExportMarkdown = async () => {
    if (!selectedProjectId) return;
    setIsExporting(true);
    setExportStatus('');
    try {
      const res = await client.get(`/projects/${selectedProjectId}/export/markdown`);
      const blob = new Blob([res.data], { type: 'text/markdown' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `clarix-sfdr-${selectedProjectId}.md`;
      a.click();
      URL.revokeObjectURL(url);
      setExportStatus('markdown');
    } catch (err) {
      console.error(err);
      alert('Export failed: ' + (err.response?.data?.detail || 'unknown error'));
    } finally {
      setIsExporting(false);
    }
  };

  const handleExportAuditZip = async () => {
    if (!selectedProjectId) return;
    setIsExporting(true);
    setExportStatus('');
    try {
      const res = await client.post(`/projects/${selectedProjectId}/audit-export`, {}, { responseType: 'blob' });
      const url = URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `clarix-audit-pack-${selectedProjectId}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      setExportStatus('audit');
    } catch (err) {
      console.error(err);
      alert('Audit export failed: ' + (err.response?.data?.detail || 'unknown error'));
    } finally {
      setIsExporting(false);
    }
  };

  const approvedCount = matrixItems.filter(i => i.answer_status === 'Approved').length;
  const draftCount = matrixItems.filter(i => i.answer_status === 'Draft').length;
  const selectedProject = (projects || []).find(p => String(p.id) === String(selectedProjectId));

  const steps = [
    { n: 1, label: 'Upload' },
    { n: 2, label: 'Generate PAI' },
    { n: 3, label: 'Review & Approve' },
    { n: 4, label: 'Export Filing' },
  ];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 w-full">
      {/* Header */}
      <div className="glass-card p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">SFDR Asset-Manager Workspace</span>
          {projects.length > 0 ? (
            <select
              className="mt-1 block w-full bg-transparent text-2xl font-bold text-slate-800 border-none outline-none focus:ring-0 cursor-pointer"
              value={selectedProjectId}
              onChange={(e) => handleProjectSelect(e.target.value)}
            >
              <option value="" disabled>Select a Project...</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
            </select>
          ) : (
            <h1 className="text-2xl font-bold text-slate-800 mt-1">No Projects Found</h1>
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className="badge badge-success flex items-center gap-1.5 text-xs px-3 py-1.5">
            <ShieldCheck size={14} /> SFDR
          </span>
          {selectedProject?.status && <span className="badge badge-default text-xs px-3 py-1.5">{selectedProject.status}</span>}
        </div>
      </div>

      {/* Stepper */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between">
          {steps.map((s, idx) => (
            <React.Fragment key={s.n}>
              <button
                onClick={() => setStep(s.n)}
                className={`flex items-center gap-3 transition-all ${step === s.n ? 'text-slate-900' : 'text-slate-400 hover:text-slate-600'}`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center font-black ${step >= s.n ? 'bg-slate-900 text-white shadow-lg shadow-slate-900/20' : 'bg-slate-100 text-slate-400'}`}>
                  {step > s.n ? <CheckCircle size={16} /> : s.n}
                </div>
                <span className="text-sm font-black uppercase tracking-wider">{s.label}</span>
              </button>
              {idx < steps.length - 1 && <div className="flex-1 h-px bg-slate-200 mx-4" />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* STEP 1 - Upload */}
      {step === 1 && (
        <div className="glass-card p-6 flex flex-col gap-6">
          <div className="flex justify-between items-center flex-wrap gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2"><UploadCloud size={18} className="text-primary-600" /> Upload investee source documents</h3>
              <p className="text-sm text-slate-500 font-medium mt-1">Sustainability reports, GHG inventories, or asset allocations used as PAI evidence.</p>
            </div>
          </div>

          <input type="file" ref={fileInputRef} onChange={handleFileUpload} className="hidden" accept=".pdf,.txt,.csv" />

          <motion.div
            onClick={() => {
              if (!selectedProjectId) { alert('Please select a project first.'); return; }
              fileInputRef.current?.click();
            }}
            className={`flex flex-col items-center justify-center p-10 border-2 border-dashed border-slate-200 rounded-xl transition-colors bg-slate-50/50 ${selectedProjectId ? 'cursor-pointer' : 'opacity-60 cursor-not-allowed'}`}
          >
            {isUploading ? (
              <div className="flex flex-col items-center">
                <Loader size={32} className="text-primary-500 animate-spin mb-4" />
                <p className="font-bold text-slate-700 text-lg mb-1">Uploading & Parsing...</p>
              </div>
            ) : (
              <>
                <UploadCloud size={32} className="text-primary-500 mb-4" />
                <p className="font-bold text-slate-700 text-lg mb-1">Click to upload documents</p>
                <p className="text-sm font-medium text-slate-400">Supports PDF, TXT, CSV</p>
              </>
            )}
          </motion.div>

          <AnimatePresence>
            {documents.length > 0 && (
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="flex flex-col gap-2 overflow-hidden">
                <h4 className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-1">Uploaded Source Documents ({documents.length})</h4>
                <div className="grid gap-2">
                  {documents.map(doc => (
                    <div key={doc.id} className="flex items-center justify-between p-3 bg-white rounded-xl border border-slate-100 shadow-sm">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-slate-50 rounded-lg flex items-center justify-center text-slate-400"><FileText size={16} /></div>
                        <div>
                          <p className="text-sm font-bold text-slate-700">{doc.file_name}</p>
                          <p className="text-[10px] font-bold text-slate-400 uppercase">{doc.source_type} • {doc.file_type}</p>
                        </div>
                      </div>
                      <span className={`text-[10px] font-black px-2 py-0.5 rounded-full ${doc.parsed_status === 'Completed' ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>{doc.parsed_status}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex justify-end pt-2">
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={() => setStep(2)}
              disabled={!selectedProjectId}
              className="btn btn-primary disabled:opacity-70 flex items-center gap-2"
            >
              Continue to Generation <ArrowRight size={16} />
            </motion.button>
          </div>
        </div>
      )}

      {/* STEP 2 - Generate PAI */}
      {step === 2 && (
        <div className="glass-card p-6 flex flex-col gap-6">
          <div>
            <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2"><Play size={18} className="text-primary-600" /> Generate PAI answers with evidence</h3>
            <p className="text-sm text-slate-500 font-medium mt-1">Extract indicators from source docs and draft PAI answers (evidence-linked) via GenAI + rules engine.</p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-5 bg-slate-50 rounded-2xl border border-slate-100">
              <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">Source Documents</p>
              <p className="text-2xl font-black text-slate-900 mt-1">{documents.length}</p>
            </div>
            <div className="p-5 bg-slate-50 rounded-2xl border border-slate-100">
              <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">PAI Indicators</p>
              <p className="text-2xl font-black text-slate-900 mt-1">{matrixItems.length}</p>
            </div>
            <div className="p-5 bg-slate-50 rounded-2xl border border-slate-100">
              <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">Draft Answers</p>
              <p className="text-2xl font-black text-slate-900 mt-1">{draftCount}</p>
            </div>
          </div>

          <div className="flex justify-end pt-2 gap-3">
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={() => setStep(1)}
              className="btn btn-secondary"
            >Back</motion.button>
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={handleGenerate}
              disabled={isProcessing || !selectedProjectId}
              className="btn btn-primary disabled:opacity-70 flex items-center gap-2"
            >
              {isProcessing ? <Loader size={16} className="animate-spin" /> : <Play size={16} fill="currentColor" />}
              {isProcessing ? 'Generating...' : 'Generate PAI Answers'}
            </motion.button>
          </div>
        </div>
      )}

      {/* STEP 3 - Review & Approve */}
      {step === 3 && (
        <div className="glass-card flex flex-col overflow-hidden">
          <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40">
            <div>
              <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2">
                <ClipboardCheck size={18} className="text-primary-600" /> Review & Approve PAI indicators
                <span className="bg-primary-100 text-primary-700 py-0.5 px-2.5 rounded-full text-xs font-black">{approvedCount}/{matrixItems.length} approved</span>
              </h3>
              <p className="text-sm text-slate-500 font-medium mt-1">Verify each evidence-linked answer before it is locked into the filing.</p>
            </div>
            <div className="flex gap-2">
              <button onClick={() => setStep(2)} className="btn btn-secondary">Back</button>
              <button
                onClick={() => setStep(4)}
                disabled={approvedCount < matrixItems.length}
                className="btn btn-primary disabled:opacity-40 flex items-center gap-2"
              >
                Continue to Export <ArrowRight size={16} />
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase tracking-wider text-slate-500 font-bold">
                  <th className="p-4 pl-6 font-semibold">Indicator</th>
                  <th className="p-4 font-semibold">RTS Code</th>
                  <th className="p-4 font-semibold">Draft Answer</th>
                  <th className="p-4 font-semibold">Status</th>
                  <th className="p-4 pr-6 font-semibold text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {isLoadingProjects ? (
                  <tr><td colSpan="5" className="p-12 text-center"><Loader size={28} className="animate-spin text-primary-600 mx-auto" /></td></tr>
                ) : matrixItems.length === 0 ? (
                  <tr><td colSpan="5" className="p-12 text-center text-slate-400 font-bold">No PAI indicators yet. Run generation from step 2.</td></tr>
                ) : (
                  matrixItems.map(item => (
                    <tr key={item.field_id} className="hover:bg-slate-50/50 transition-colors">
                      <td className="p-4 pl-6">
                        <span className="font-bold text-slate-800 text-sm">{item.field_label}</span>
                        <span className="block text-[10px] text-slate-400 font-bold uppercase">{item.annex_code}</span>
                      </td>
                      <td className="p-4"><code className="text-[11px] bg-slate-100 text-slate-600 px-2 py-1 rounded font-mono">{item.field_code}</code></td>
                      <td className="p-4 font-bold text-slate-700 text-sm max-w-[260px] truncate">
                        {item.answer_text ? (item.answer_text.length > 60 ? item.answer_text.substring(0, 60) + '...' : item.answer_text) : '-'}
                      </td>
                      <td className="p-4">
                        <span className={`badge ${item.answer_status === 'Approved' ? 'badge-success' : item.answer_status === 'Rejected' ? 'badge-danger' : 'badge-default'}`}>
                          {item.answer_status}
                        </span>
                      </td>
                      <td className="p-4 pr-6">
                        <div className="flex justify-end gap-2">
                          <button
                            onClick={() => handleReject(item)}
                            disabled={isProcessing}
                            className="p-2 rounded-lg text-rose-500 hover:bg-rose-50 transition-colors disabled:opacity-40"
                            title="Reject"
                          >
                            <XCircle size={18} />
                          </button>
                          <button
                            onClick={() => handleApprove(item)}
                            disabled={isProcessing}
                            className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-40"
                            title="Approve"
                          >
                            <CheckCircle size={18} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* STEP 4 - Export */}
      {step === 4 && (
        <div className="glass-card p-6 flex flex-col gap-6">
          <div>
            <h3 className="font-bold text-lg text-slate-800 flex items-center gap-2"><Package size={18} className="text-primary-600" /> Export the filing package</h3>
            <p className="text-sm text-slate-500 font-medium mt-1">Download the SFDR PAI answers as a document, or the full audit-ready evidence pack.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-4">
            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={handleExportMarkdown}
              disabled={isExporting}
              className="p-6 bg-slate-50 rounded-2xl border border-slate-100 text-left hover:border-primary-200 hover:bg-primary-50/40 transition-all disabled:opacity-50"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 bg-white rounded-xl shadow-sm flex items-center justify-center"><Download size={18} className="text-primary-600" /></div>
              </div>
              <p className="font-black text-slate-800">Markdown Filing</p>
              <p className="text-xs text-slate-400 font-medium mt-1">SFDR PAI answers as Markdown document.</p>
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              onClick={handleExportAuditZip}
              disabled={isExporting}
              className="p-6 bg-slate-50 rounded-2xl border border-slate-100 text-left hover:border-primary-200 hover:bg-primary-50/40 transition-all disabled:opacity-50"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 bg-white rounded-xl shadow-sm flex items-center justify-center"><Package size={18} className="text-primary-600" /></div>
              </div>
              <p className="font-black text-slate-800">Audit Evidence Pack (ZIP)</p>
              <p className="text-xs text-slate-400 font-medium mt-1">Final report, source docs, integrity + evidence-mapping CSVs.</p>
            </motion.button>

            <motion.div
              whileHover={{ scale: 1.02 }}
              className="p-6 bg-slate-900 rounded-2xl text-white"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center"><BarChart3 size={18} className="text-white" /></div>
                <span className="text-[10px] font-black text-white/30 uppercase">This project</span>
              </div>
              <p className="font-black">{approvedCount}/{matrixItems.length} indicators approved</p>
              <p className="text-xs text-white/50 font-medium mt-1">Review ESG-feed coverage for investee data availability on the ESG Feed page.</p>
            </motion.div>
          </div>

          {exportStatus && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-700 font-bold text-sm">
              {exportStatus === 'markdown' ? 'Markdown filing downloaded successfully.' : 'Audit evidence pack downloaded successfully.'}
            </motion.div>
          )}

          <div className="flex justify-end pt-2">
            <button onClick={() => setStep(3)} className="btn btn-secondary flex items-center gap-2"><ArrowRight size={16} className="rotate-180" /> Back to Review</button>
          </div>
        </div>
      )}
    </motion.div>
  );
};

export default SfdrCoreLoop;