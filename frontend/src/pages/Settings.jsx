import React from 'react';
import { Save, Key, Cpu, Zap } from 'lucide-react';
import { motion } from 'framer-motion';

const Settings = () => {
  return (
    <motion.div 
      initial={{ opacity: 0 }} animate={{ opacity: 1 }}
      className="flex flex-col gap-6 w-full max-w-4xl mx-auto"
    >
      {/* Top Bar */}
      <div className="glass-card p-6 flex justify-between items-start md:items-center flex-wrap gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">System Preferences</span>
          <h1 className="text-3xl font-bold text-slate-800 mt-1 tracking-tight">Workspace Configuration</h1>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Sidebar Nav (mock) */}
        <div className="md:col-span-1 flex flex-col gap-2">
          <button className="flex items-center gap-3 px-4 py-3 rounded-xl bg-primary-50 text-primary-700 font-bold shadow-[inset_0_1px_0_white,0_1px_3px_rgba(0,0,0,0.02)] border border-primary-100 transition-all">
            <Cpu size={18} /> LLM Engine
          </button>
          <button className="flex items-center gap-3 px-4 py-3 rounded-xl text-slate-600 hover:bg-white/60 hover:text-slate-900 font-semibold transition-all">
            <Zap size={18} /> Integrations
          </button>
        </div>

        {/* Main Settings Area */}
        <motion.div 
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.1 }}
          className="md:col-span-2 glass-card p-8 flex flex-col gap-8"
        >
          <div className="flex items-center gap-3 border-b border-slate-100 pb-4">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-md shadow-indigo-500/20">
              <Key size={20} />
            </div>
            <div>
              <h3 className="font-bold text-xl text-slate-800">Groq LLM Configuration</h3>
              <p className="text-sm font-medium text-slate-500 mt-1">Configure your blazing fast inference engine.</p>
            </div>
          </div>
          
          <div className="flex flex-col gap-6">
            <div className="form-group flex flex-col gap-2">
              <label className="text-sm font-bold text-slate-700">Groq API Key</label>
              <div className="relative">
                <input 
                  type="password" 
                  className="form-input pl-4 pr-10 py-3 font-mono text-lg shadow-inner bg-slate-50/50" 
                  placeholder="gsk_..." 
                  defaultValue="gsk_mock_key_12345"
                />
              </div>
              <p className="text-xs font-semibold text-slate-400 mt-1 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                Your key is stored securely in local browser storage.
              </p>
            </div>

            <div className="form-group p-4 bg-slate-50/50 border border-slate-200 rounded-xl">
              <label className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-2 block">Active Engine Status</label>
              <div className="flex items-center gap-3">
                <div className="w-3 h-3 rounded-full bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.8)] animate-pulse"></div>
                <div className="font-bold text-slate-800 flex items-center gap-2">
                  Connected to <span className="px-2 py-0.5 bg-white border border-slate-200 rounded text-xs font-mono">llama3-8b-8192</span>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-100 flex justify-end">
              <motion.button 
                whileHover={{ scale: 1.02 }} 
                whileTap={{ scale: 0.98 }} 
                className="btn btn-primary px-6 py-2.5 shadow-primary-500/30 font-bold"
              >
                <Save size={18} /> Update Configuration
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};

export default Settings;
