import React, { useState, useEffect } from 'react';
import { ShieldCheck, Table, Download, RefreshCw, FileText, Search, ChevronDown, ChevronUp, Loader } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const AuditorPortal = () => {
  const { projects, isLoadingProjects } = useProjects();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [ledger, setLedger] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [isDataLoading, setIsDataLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [isVerifyingDocs, setIsVerifyingDocs] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedRows, setExpandedRows] = useState({});

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  // Fetch auditor ledger and project documents when project changes
  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchAuditorData = async () => {
      setIsDataLoading(true);
      try {
        const ledgerRes = await client.get(`/projects/${selectedProjectId}/auditor-ledger`);
        setLedger(ledgerRes.data);

        const docsRes = await client.get(`/projects/${selectedProjectId}/documents`);
        // Verify each document integrity
        const docsWithStatus = await Promise.all(
          docsRes.data.map(async (doc) => {
            try {
              const integrityRes = await client.get(`/documents/${doc.id}/integrity`);
              return { ...doc, integrity: integrityRes.data };
            } catch {
              return { ...doc, integrity: { integrity_status: 'TAMPERED', current_hash: 'Error' } };
            }
          })
        );
        setDocuments(docsWithStatus);
      } catch (err) {
        console.error("Failed to fetch auditor data", err);
      } finally {
        setIsDataLoading(false);
      }
    };
    fetchAuditorData();
  }, [selectedProjectId]);

  const toggleRow = (id) => {
    setExpandedRows(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleVerifyAllDocuments = async () => {
    if (!selectedProjectId) return;
    setIsVerifyingDocs(true);
    try {
      const docsRes = await client.get(`/projects/${selectedProjectId}/documents`);
      const docsWithStatus = await Promise.all(
        docsRes.data.map(async (doc) => {
          try {
            const integrityRes = await client.get(`/documents/${doc.id}/integrity`);
            return { ...doc, integrity: integrityRes.data };
          } catch {
            return { ...doc, integrity: { integrity_status: 'TAMPERED', current_hash: 'Error' } };
          }
        })
      );
      setDocuments(docsWithStatus);
      // Re-fetch ledger to ensure integrity statuses are updated
      const ledgerRes = await client.get(`/projects/${selectedProjectId}/auditor-ledger`);
      setLedger(ledgerRes.data);
    } catch (err) {
      console.error("Failed to verify document integrity", err);
    } finally {
      setIsVerifyingDocs(false);
    }
  };

  const handleExportZip = async () => {
    if (!selectedProjectId) return;
    setIsExporting(true);
    try {
      const response = await client.post(
        `/projects/${selectedProjectId}/audit-export`,
        {},
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Audit_Export_Package_${selectedProjectId}.zip`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export failed", err);
      alert("Failed to export audit package.");
    } finally {
      setIsExporting(false);
    }
  };

  const filteredLedger = ledger.filter(item => {
    const q = searchQuery.toLowerCase();
    return (
      (item.field_code || '').toLowerCase().includes(q) ||
      (item.field_label || '').toLowerCase().includes(q) ||
      (item.final_value || '').toLowerCase().includes(q) ||
      (item.document_name || '').toLowerCase().includes(q)
    );
  });

  // Calculate high-level stats
  const totalLedgerFields = ledger.length;
  const verifiedLedgerFields = ledger.filter(l => l.integrity_verified).length;
  const tamperedDocsCount = documents.filter(d => d.integrity?.integrity_status !== 'INTACT').length;

  if (isLoadingProjects) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <div className="w-10 h-10 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin"></div>
        <div className="text-slate-500 font-bold">Loading Auditor Portal...</div>
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }} 
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-6 w-full max-w-6xl mx-auto"
    >
      {/* Header bar */}
      <div className="glass-card p-6 flex justify-between items-center flex-wrap gap-4 shadow-sm">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Reasonable Assurance Audit</span>
            {selectedProject?.status === 'Completed' && (
              <span className="badge badge-success text-[10px] py-0.5 px-2">
                Completed & Ready
              </span>
            )}
          </div>
          {projects.length > 0 ? (
            <select 
              className="mt-1 block w-full bg-transparent text-3xl font-bold text-slate-800 border-none outline-none focus:ring-0 cursor-pointer p-0"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
            >
              <option value="" disabled>Select a Project to Audit...</option>
              {projects.map(p => (
                <option key={p.id} value={p.id} className="text-sm">{p.name}</option>
              ))}
            </select>
          ) : (
            <h1 className="text-3xl font-bold text-slate-800 mt-1 tracking-tight">No Active Projects</h1>
          )}
        </div>

        {selectedProjectId && (
          <div className="flex items-center gap-3">
            <button 
              onClick={handleVerifyAllDocuments}
              disabled={isVerifyingDocs}
              className="btn btn-secondary border-none shadow-none bg-slate-100 hover:bg-slate-200/80 flex items-center gap-2"
            >
              <RefreshCw size={16} className={isVerifyingDocs ? 'animate-spin' : ''} />
              <span className="font-semibold text-slate-700">Recheck Integrity</span>
            </button>
            
            <button 
              onClick={handleExportZip}
              disabled={isExporting}
              className="btn btn-primary flex items-center gap-2 font-semibold shadow-lg shadow-primary-500/20"
            >
              {isExporting ? <Loader size={16} className="animate-spin" /> : <Download size={16} />}
              <span>Export Audit Package</span>
            </button>
          </div>
        )}
      </div>

      {selectedProjectId ? (
        <>
          {/* Key Audit Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="glass-card p-6 flex items-center justify-between border-l-4 border-l-primary-500">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Reported & Logged Fields</p>
                <h3 className="text-3xl font-bold text-slate-800 mt-2">{totalLedgerFields}</h3>
                <p className="text-xs text-slate-400 mt-1">Total verified audit items</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-primary-50 flex items-center justify-center text-primary-600">
                <Table size={24} />
              </div>
            </div>

            <div className="glass-card p-6 flex items-center justify-between border-l-4 border-l-emerald-500">
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Assurance Approvals</p>
                <h3 className="text-3xl font-bold text-slate-800 mt-2">{verifiedLedgerFields}</h3>
                <p className="text-xs text-slate-400 mt-1">{totalLedgerFields > 0 ? `${Math.round((verifiedLedgerFields / totalLedgerFields) * 100)}%` : '0%'} chain verified</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600">
                <ShieldCheck size={24} />
              </div>
            </div>

            <div className={`glass-card p-6 flex items-center justify-between border-l-4 ${tamperedDocsCount > 0 ? 'border-l-rose-500' : 'border-l-indigo-500'}`}>
              <div>
                <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Tamper Verification Status</p>
                <h3 className={`text-3xl font-bold mt-2 ${tamperedDocsCount > 0 ? 'text-rose-600' : 'text-slate-800'}`}>
                  {tamperedDocsCount > 0 ? `${tamperedDocsCount} Faulty` : 'All Intact'}
                </h3>
                <p className="text-xs text-slate-400 mt-1">Stored SHA-256 byte comparison</p>
              </div>
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${tamperedDocsCount > 0 ? 'bg-rose-50 text-rose-600 animate-pulse' : 'bg-indigo-50 text-indigo-600'}`}>
                <FileText size={24} />
              </div>
            </div>
          </div>

          {/* Document Integrity Checklist */}
          <div className="glass-card p-6">
            <h3 className="font-bold text-lg text-slate-800 mb-4 flex items-center gap-2">
              <FileText size={18} className="text-slate-500" />
              Source Documents Ledger & Hash Mapping
            </h3>
            {documents.length === 0 ? (
              <p className="text-sm text-slate-500">No documents uploaded for this project yet.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {documents.map(doc => {
                  const integrityStatus = doc.integrity?.integrity_status || 'INTACT';
                  return (
                    <div 
                      key={doc.id}
                      className={`p-4 rounded-xl border flex flex-col gap-2 transition-all ${
                        integrityStatus === 'INTACT' 
                          ? 'bg-emerald-50/20 border-emerald-100 hover:border-emerald-200' 
                          : 'bg-rose-50/20 border-rose-100 hover:border-rose-200'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <h4 className="font-bold text-slate-700 text-sm truncate max-w-xs">{doc.file_name}</h4>
                          <p className="text-[10px] text-slate-400 mt-0.5 font-semibold uppercase">{doc.source_type}</p>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase ${
                          integrityStatus === 'INTACT' 
                            ? 'bg-emerald-100 text-emerald-800' 
                            : 'bg-rose-100 text-rose-800 animate-pulse'
                        }`}>
                          {integrityStatus === 'INTACT' ? '✓ Intact' : '⚠ Tampered'}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500 font-mono flex flex-col gap-0.5 bg-white/40 p-2 rounded-lg border border-slate-100 mt-1">
                        <div><span className="font-bold text-slate-700">Stored SHA256:</span> {doc.file_hash ? doc.file_hash.substring(0, 16) + '...' : 'None'}</div>
                        <div><span className="font-bold text-slate-700">Current SHA256:</span> {doc.integrity?.current_hash ? doc.integrity.current_hash.substring(0, 16) + '...' : 'None'}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Searchable Auditor Ledger */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <div className="flex justify-between items-center flex-wrap gap-4 border-b border-slate-100 pb-4">
              <div>
                <h3 className="font-bold text-xl text-slate-800">Evidence Mapping Trail</h3>
                <p className="text-sm text-slate-500 mt-1">Audit-ready validation data generated automatically upon field review approvals.</p>
              </div>
              
              {/* Search Bar */}
              <div className="relative w-full sm:w-72">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input 
                  type="text"
                  placeholder="Search field, values or sources..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20 focus:border-primary-500 transition-all bg-slate-50/50"
                />
              </div>
            </div>

            {isDataLoading ? (
              <div className="flex flex-col items-center justify-center py-12 gap-3 text-slate-500">
                <div className="w-8 h-8 border-4 border-slate-200 border-t-primary-600 rounded-full animate-spin"></div>
                <span className="font-bold text-sm">Loading evidence trail...</span>
              </div>
            ) : filteredLedger.length === 0 ? (
              <div className="text-center py-12 text-slate-500 font-medium">
                {searchQuery ? "No entries match your search query." : "No fields approved and recorded in the auditor ledger yet."}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-slate-100 text-[11px] font-bold text-slate-400 uppercase tracking-wider bg-slate-50/50">
                      <th className="py-3 px-4">Field Details</th>
                      <th className="py-3 px-4">Reported Value</th>
                      <th className="py-3 px-4">Source Document</th>
                      <th className="py-3 px-4">Integrity</th>
                      <th className="py-3 px-4">Reviewer Approval</th>
                      <th className="py-3 px-4 text-center">Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredLedger.map((item) => {
                      const isExpanded = expandedRows[item.id];
                      return (
                        <React.Fragment key={item.id}>
                          <tr className="border-b border-slate-100/50 hover:bg-slate-50/30 transition-colors text-sm text-slate-700">
                            <td className="py-4 px-4">
                              <div className="font-bold text-slate-800">{item.field_label}</div>
                              <div className="text-[10px] text-slate-400 font-mono mt-0.5">{item.field_code}</div>
                            </td>
                            <td className="py-4 px-4 font-semibold text-slate-800 max-w-xs truncate">
                              {item.final_value || <span className="text-slate-400 italic">None</span>}
                            </td>
                            <td className="py-4 px-4">
                              <div className="font-medium text-slate-800">{item.document_name || 'N/A'}</div>
                              <div className="text-[10px] text-slate-500">
                                {item.source_page ? `Page ${item.source_page}` : 'No page citation'}
                              </div>
                            </td>
                            <td className="py-4 px-4">
                              <span className={`px-2.5 py-1 rounded-full text-[10px] font-extrabold uppercase tracking-wide flex items-center gap-1 w-fit ${
                                item.document_hash 
                                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' 
                                  : 'bg-slate-50 text-slate-500 border border-slate-100'
                              }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${item.document_hash ? 'bg-emerald-500' : 'bg-slate-400'}`}></span>
                                {item.document_hash ? 'Verified Hash' : 'Unhashed'}
                              </span>
                            </td>
                            <td className="py-4 px-4">
                              <div className="font-semibold text-slate-700">{item.approver_username || 'System'}</div>
                              <div className="text-[10px] text-slate-400 mt-0.5">
                                {item.approval_timestamp ? new Date(item.approval_timestamp).toLocaleDateString() : 'N/A'}
                              </div>
                            </td>
                            <td className="py-4 px-4 text-center">
                              <button 
                                onClick={() => toggleRow(item.id)}
                                className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
                              >
                                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                              </button>
                            </td>
                          </tr>
                          
                          {/* Expanded Detail Panel */}
                          <AnimatePresence>
                            {isExpanded && (
                              <tr>
                                <td colSpan="6" className="py-0 px-4">
                                  <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: 'auto' }}
                                    exit={{ opacity: 0, height: 0 }}
                                    transition={{ duration: 0.2 }}
                                    className="overflow-hidden bg-slate-50/50 p-4 rounded-xl border border-slate-100 my-2 text-xs text-slate-600 flex flex-col gap-3"
                                  >
                                    <div>
                                      <h5 className="font-bold text-slate-700 uppercase tracking-wider text-[9px] mb-1">Direct Audit Quote / Evidence Passage</h5>
                                      <p className="bg-white p-3 rounded-lg border border-slate-100 italic text-slate-700 shadow-sm leading-relaxed">
                                        "{item.source_passage || 'No matching source quote recorded.'}"
                                      </p>
                                    </div>
                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                      <div>
                                        <h5 className="font-bold text-slate-700 uppercase tracking-wider text-[9px]">Extraction Model</h5>
                                        <p className="text-slate-600 mt-1 font-mono text-[11px]">{item.extraction_model || 'N/A'}</p>
                                      </div>
                                      <div>
                                        <h5 className="font-bold text-slate-700 uppercase tracking-wider text-[9px]">Timestamp</h5>
                                        <p className="text-slate-600 mt-1">{item.extraction_timestamp ? new Date(item.extraction_timestamp).toLocaleString() : 'N/A'}</p>
                                      </div>
                                      <div>
                                        <h5 className="font-bold text-slate-700 uppercase tracking-wider text-[9px]">Document SHA-256</h5>
                                        <p className="text-slate-600 mt-1 font-mono break-all text-[10px]">{item.document_hash || 'N/A'}</p>
                                      </div>
                                    </div>
                                  </motion.div>
                                </td>
                              </tr>
                            )}
                          </AnimatePresence>
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="p-12 text-center text-slate-500 font-medium glass-card">
          Please select a project from the workspace selector dropdown above to display the audit logs.
        </div>
      )}
    </motion.div>
  );
};

export default AuditorPortal;
