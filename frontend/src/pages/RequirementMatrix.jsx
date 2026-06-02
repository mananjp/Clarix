import React, { useState, useEffect, useRef } from 'react';
import { UploadCloud, Search, Download, Play, Filter, Loader } from 'lucide-react';
import { motion } from 'framer-motion';
import client from '../api/client';

const containerVariants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { staggerChildren: 0.05 } }
};

const rowVariants = {
  hidden: { opacity: 0, x: -10 },
  show: { opacity: 1, x: 0 }
};

const RequirementMatrix = () => {
  const [projects, setProjects] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [matrixItems, setMatrixItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  
  const fileInputRef = useRef(null);

  // Fetch projects on mount
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        const res = await client.get('/projects');
        setProjects(res.data);
        if (res.data.length > 0) {
          setSelectedProjectId(res.data[0].id);
        }
      } catch (err) {
        console.error("Failed to fetch projects", err);
      } finally {
        setLoading(false);
      }
    };
    fetchProjects();
  }, []);

  // Fetch matrix when selected project changes
  useEffect(() => {
    if (!selectedProjectId) return;
    const fetchMatrix = async () => {
      try {
        const res = await client.get(`/projects/${selectedProjectId}/matrix`);
        setMatrixItems(res.data);
      } catch (err) {
        console.error("Failed to fetch matrix", err);
      }
    };
    fetchMatrix();
  }, [selectedProjectId]);

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !selectedProjectId) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', 'sustainability_report'); // default for now

    try {
      await client.post(`/projects/${selectedProjectId}/documents`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      alert('Document uploaded and parsed successfully!');
    } catch (err) {
      console.error("Upload failed", err);
      alert('Failed to upload document.');
    } finally {
      setIsUploading(false);
      e.target.value = null; // reset input
    }
  };

  const handleExecuteGenAI = async () => {
    if (!selectedProjectId) return;
    setIsProcessing(true);
    try {
      await client.post(`/projects/${selectedProjectId}/process`);
      // Refetch matrix after processing
      const res = await client.get(`/projects/${selectedProjectId}/matrix`);
      setMatrixItems(res.data);
      alert('GenAI Extraction & Drafting Complete!');
    } catch (err) {
      console.error("GenAI processing failed", err);
      alert(err.response?.data?.detail || 'Failed to process document. Please ensure documents are uploaded first.');
    } finally {
      setIsProcessing(false);
    }
  };

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  if (loading) {
    return <div className="p-8 text-slate-500 font-medium">Loading workspace data...</div>;
  }

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 w-full">
      {/* Top Bar */}
      <div className="glass-card p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Active Workspace</span>
          {projects.length > 0 ? (
            <select 
              className="mt-1 block w-full bg-transparent text-2xl font-bold text-slate-800 border-none outline-none focus:ring-0 cursor-pointer"
              value={selectedProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
            >
              {projects.map(p => (
                <option key={p.id} value={p.id} className="text-sm">{p.name}</option>
              ))}
            </select>
          ) : (
            <h1 className="text-2xl font-bold text-slate-800 mt-1">No Projects Found</h1>
          )}
        </div>
        <div className="flex gap-3">
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-secondary">
            Run Rules Engine
          </motion.button>
          <motion.button 
            whileHover={{ scale: 1.02 }} 
            whileTap={{ scale: 0.98 }} 
            onClick={handleExecuteGenAI}
            disabled={isProcessing || !selectedProjectId}
            className="btn btn-primary shadow-primary-500/30 disabled:opacity-70"
          >
            {isProcessing ? <Loader size={16} className="animate-spin" /> : <Play size={16} fill="currentColor" />}
            <span>{isProcessing ? 'Processing...' : 'Execute GenAI'}</span>
          </motion.button>
        </div>
      </div>

      {/* Document Ingestion Card */}
      <div className="glass-card p-6 flex flex-col gap-6">
        <div className="flex justify-between items-center flex-wrap gap-4 border-b border-slate-100 pb-4">
          <div>
            <h3 className="font-bold text-lg text-slate-800">1. Document Ingest & OCR</h3>
            <p className="text-sm text-slate-500 font-medium mt-1">Upload sustainability reports or asset allocations.</p>
          </div>
        </div>

        <input 
          type="file" 
          ref={fileInputRef}
          onChange={handleFileUpload}
          className="hidden" 
          accept=".pdf,.txt,.csv"
        />

        <motion.div 
          whileHover={{ borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.05)' }}
          onClick={() => fileInputRef.current?.click()}
          className="flex flex-col items-center justify-center p-10 border-2 border-dashed border-slate-200 rounded-xl transition-colors cursor-pointer bg-slate-50/50" 
        >
          {isUploading ? (
            <div className="flex flex-col items-center">
              <Loader size={32} className="text-primary-500 animate-spin mb-4" />
              <p className="font-bold text-slate-700 text-lg mb-1">Uploading & Parsing...</p>
            </div>
          ) : (
            <>
              <motion.div
                animate={{ y: [0, -6, 0] }}
                transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
                className="w-16 h-16 bg-white rounded-full shadow-sm flex items-center justify-center mb-4"
              >
                <UploadCloud size={32} className="text-primary-500" />
              </motion.div>
              <p className="font-bold text-slate-700 text-lg mb-1">Click to upload files</p>
              <p className="text-sm font-medium text-slate-400">Supports PDF, TXT, CSV</p>
            </>
          )}
        </motion.div>
      </div>

      {/* Matrix Table */}
      <div className="glass-card flex flex-col overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40">
          <h3 className="font-bold text-lg text-slate-800">2. SFDR Compliance Matrix</h3>
          
          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input type="text" className="form-input pl-9 bg-white/50" placeholder="Search requirements..." />
            </div>
            <button className="btn btn-secondary"><Download size={16} /> Export</button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase tracking-wider text-slate-500 font-bold">
                <th className="p-4 pl-6 font-semibold">Disclosure Requirement</th>
                <th className="p-4 font-semibold">RTS Code</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Extracted Value</th>
                <th className="p-4 pr-6 font-semibold">Validation</th>
              </tr>
            </thead>
            <motion.tbody variants={containerVariants} initial="hidden" animate="show" className="divide-y divide-slate-100">
              {matrixItems.length === 0 ? (
                <tr><td colSpan="5" className="p-8 text-center text-slate-500 font-medium">No matrix data available.</td></tr>
              ) : matrixItems.map(item => (
                <motion.tr variants={rowVariants} key={item.field_id} className="hover:bg-slate-50/50 transition-colors group cursor-pointer">
                  <td className="p-4 pl-6">
                    <span className="font-bold text-slate-800 group-hover:text-primary-600 transition-colors">{item.field_label}</span>
                    {item.mandatory && <span className="text-rose-500 ml-1 font-bold">*</span>}
                  </td>
                  <td className="p-4">
                    <code className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-md font-mono border border-slate-200">{item.field_code}</code>
                  </td>
                  <td className="p-4">
                    <span className={`badge ${
                      item.answer_status === 'Approved' ? 'badge-success' : 
                      item.answer_status === 'Draft' ? 'bg-indigo-50 text-indigo-700' : 'badge-danger'
                    }`}>
                      {item.answer_status}
                    </span>
                  </td>
                  <td className="p-4 font-semibold text-slate-700 max-w-xs truncate">
                    {item.extracted_value?.value || item.extracted_value || '-'}
                  </td>
                  <td className="p-4 pr-6">
                    <span className={`text-sm font-bold flex items-center gap-1.5 ${item.validation_passed ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {item.validation_passed && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>}
                      {!item.validation_passed && <div className="w-1.5 h-1.5 rounded-full bg-rose-500"></div>}
                      {item.validation_passed ? 'Passed' : 'Issues Found'}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </motion.tbody>
          </table>
        </div>
      </div>
    </motion.div>
  );
};

export default RequirementMatrix;
