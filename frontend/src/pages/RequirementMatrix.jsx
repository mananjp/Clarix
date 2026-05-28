import React, { useState } from 'react';
import { UploadCloud, Search, Download, Play, Filter } from 'lucide-react';
import { motion } from 'framer-motion';

const containerVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 }
  }
};

const rowVariants = {
  hidden: { opacity: 0, x: -10 },
  show: { opacity: 1, x: 0 }
};

const RequirementMatrix = () => {
  const [matrixItems] = useState([
    {
      id: 1,
      requirement: 'GHG Scope 1 Emissions',
      code: 'PAI_GHG_SCOPE1',
      annex: 'Annex I',
      status: 'Approved',
      extracted: '14,230 tCO2e',
      validation: 'Passed',
      mandatory: true
    },
    {
      id: 2,
      requirement: 'Carbon Footprint',
      code: 'PAI_CARBON_FOOTPRINT',
      annex: 'Annex I',
      status: 'Draft',
      extracted: '120.5 tCO2e/€M',
      validation: 'Passed',
      mandatory: true
    },
    {
      id: 3,
      requirement: 'Board Gender Diversity',
      code: 'PAI_BOARD_GENDER',
      annex: 'Annex I',
      status: 'Rejected',
      extracted: 'N/A',
      validation: 'Failed: Missing value',
      mandatory: true
    }
  ]);

  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} 
      className="flex flex-col gap-6 w-full"
    >
      {/* Top Bar */}
      <div className="glass-card p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Active Workspace</span>
          <h1 className="text-2xl font-bold text-slate-800 mt-1">Global Climate Impact Fund 2026</h1>
        </div>
        <div className="flex gap-3">
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-secondary">
            Run Rules Engine
          </motion.button>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="btn btn-primary shadow-primary-500/30">
            <Play size={16} fill="currentColor" />
            <span>Execute GenAI</span>
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
          <select className="form-input w-48 bg-white/50">
            <option>Sustainability Report</option>
            <option>Annual Report</option>
            <option>Factsheet</option>
          </select>
        </div>

        <motion.div 
          whileHover={{ borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.05)' }}
          className="flex flex-col items-center justify-center p-10 border-2 border-dashed border-slate-200 rounded-xl transition-colors cursor-pointer bg-slate-50/50" 
        >
          <motion.div
            animate={{ y: [0, -6, 0] }}
            transition={{ repeat: Infinity, duration: 2.5, ease: "easeInOut" }}
            className="w-16 h-16 bg-white rounded-full shadow-sm flex items-center justify-center mb-4"
          >
            <UploadCloud size={32} className="text-primary-500" />
          </motion.div>
          <p className="font-bold text-slate-700 text-lg mb-1">Drag & drop files here</p>
          <p className="text-sm font-medium text-slate-400">Supports PDF, TXT, CSV (Multi-file upload supported)</p>
        </motion.div>
      </div>

      {/* Matrix Table */}
      <div className="glass-card flex flex-col overflow-hidden">
        <div className="p-6 border-b border-slate-100 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40">
          <h3 className="font-bold text-lg text-slate-800">2. SFDR Compliance Matrix</h3>
          
          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input type="text" className="form-input pl-9 bg-white/50" placeholder="Search parameters..." />
            </div>
            <button className="btn btn-secondary px-3">
              <Filter size={16} />
            </button>
            <button className="btn btn-secondary">
              <Download size={16} /> Export
            </button>
          </div>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/50 border-b border-slate-100 text-xs uppercase tracking-wider text-slate-500 font-bold">
                <th className="p-4 pl-6 font-semibold">Disclosure Requirement</th>
                <th className="p-4 font-semibold">RTS Code</th>
                <th className="p-4 font-semibold">Annex</th>
                <th className="p-4 font-semibold">Status</th>
                <th className="p-4 font-semibold">Extracted Value</th>
                <th className="p-4 pr-6 font-semibold">Validation</th>
              </tr>
            </thead>
            <motion.tbody variants={containerVariants} initial="hidden" animate="show" className="divide-y divide-slate-100">
              {matrixItems.map(item => (
                <motion.tr variants={rowVariants} key={item.id} className="hover:bg-slate-50/50 transition-colors group cursor-pointer">
                  <td className="p-4 pl-6">
                    <span className="font-bold text-slate-800 group-hover:text-primary-600 transition-colors">{item.requirement}</span>
                    {item.mandatory && <span className="text-rose-500 ml-1 font-bold">*</span>}
                  </td>
                  <td className="p-4">
                    <code className="text-xs bg-slate-100 text-slate-600 px-2 py-1 rounded-md font-mono border border-slate-200">{item.code}</code>
                  </td>
                  <td className="p-4 text-sm font-medium text-slate-500">{item.annex}</td>
                  <td className="p-4">
                    <span className={`badge ${
                      item.status === 'Approved' ? 'badge-success' : 
                      item.status === 'Draft' ? 'badge-default' : 'badge-danger'
                    }`}>
                      {item.status}
                    </span>
                  </td>
                  <td className="p-4 font-semibold text-slate-700">{item.extracted}</td>
                  <td className="p-4 pr-6">
                    <span className={`text-sm font-bold flex items-center gap-1.5 ${item.validation === 'Passed' ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {item.validation === 'Passed' && <div className="w-1.5 h-1.5 rounded-full bg-emerald-500"></div>}
                      {item.validation !== 'Passed' && <div className="w-1.5 h-1.5 rounded-full bg-rose-500"></div>}
                      {item.validation}
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
