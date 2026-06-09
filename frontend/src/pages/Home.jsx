import React from 'react';
import {
  ShieldAlert,
  ArrowRight,
  CheckCircle2,
  FileSearch,
  GitBranch,
  Download,
  TrendingUp,
  AlertTriangle,
  Users,
  ChevronRight,
  Zap,
  Database,
  BookOpen,
  Globe,
  Cpu,
  Lock,
  Play,
  Layers,
  Terminal,
  Activity,
  Box,
  Binary,
  ShieldCheck,
  FileCode,
  Link
} from "lucide-react";
import { motion } from "framer-motion";
import { Link as RouterLink } from 'react-router-dom';

const FEATURES = [
  {
    icon: <Binary className="w-5 h-5" />,
    title: "Immutable Evidence",
    desc: "Every metric is cryptographically hashed and linked to source document chunks. No generative hallucinations — only verifiable data extraction.",
    code: "SHA-256 PROVENANCE"
  },
  {
    icon: <ShieldCheck className="w-5 h-5" />,
    title: "Mandatory-Field Guardrails",
    desc: "Automated rule validation against RTS/ESRS technical standards. Prevents submission of incomplete or non-compliant disclosure packages.",
    code: "VALIDATION_ENGINE_V2"
  },
  {
    icon: <Users className="w-5 h-5" />,
    title: "Audit Workflow",
    desc: "Rigorous Approve/Reject cycles with full reviewer identity persistence. Maintains a granular audit trail for every field modification.",
    code: "SECURE_OPS_LAYER"
  },
  {
    icon: <FileCode className="w-5 h-5" />,
    title: "Structured Outputs",
    desc: "Exports disclosure-ready data in Markdown, CSV, and HTML. Optimized for regulatory submission and internal audit verification.",
    code: "PORTABLE_DOC_SCHEMA"
  },
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05
    }
  }
};

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: "easeOut" } }
};

export default function Home() {
  return (
    <div className="min-h-screen bg-white font-mono text-slate-900 selection:bg-slate-900 selection:text-white overflow-x-hidden">
      {/* Grid Overlay */}
      <div className="fixed inset-0 pointer-events-none opacity-[0.03] z-0" style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '32px 32px' }}></div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-200">
        <div className="max-w-[1400px] mx-auto px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-slate-900 rounded-sm flex items-center justify-center text-white">
              <ShieldAlert size={16} strokeWidth={2.5} />
            </div>
            <span className="font-black text-xl tracking-tighter uppercase">Clarix</span>
          </div>

          <div className="hidden lg:flex items-center gap-10">
            <a href="#features" className="text-[10px] font-black text-slate-400 hover:text-slate-900 transition-all uppercase tracking-[0.2em]">01. Protocol</a>
            <a href="#audit" className="text-[10px] font-black text-slate-400 hover:text-slate-900 transition-all uppercase tracking-[0.2em]">02. Audit</a>
            <div className="h-4 w-px bg-slate-200"></div>
            <RouterLink to="/login" className="text-[10px] font-black text-slate-500 hover:text-slate-900 transition-all uppercase tracking-[0.2em]">Sign In</RouterLink>
            <RouterLink
              to="/signup"
              className="px-6 py-2 bg-slate-900 text-white rounded-sm text-[10px] font-black hover:bg-slate-800 transition-all active:scale-95 uppercase tracking-[0.2em]"
            >
              Initialize Workspace
            </RouterLink>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-40 pb-32 px-8">
        <div className="max-w-[1400px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-3 mb-10">
              <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em]">Operational Readiness / SFDR • CSRD • BRSR</span>
            </div>

            <h1 className="text-6xl md:text-8xl font-black tracking-tighter text-slate-900 mb leading-[0.9] max-w-5xl">
              DETERMINISTIC <br />
              COMPLIANCE.
            </h1>

            <p className="text-xl text-slate-500 font-bold max-w-2xl mb-16 leading-relaxed font-sans">
              High-integrity data extraction for regulatory disclosures. Built for deterministic evidence-linking, not generative speculation.
            </p>

            <div className="flex flex-col sm:flex-row items-center gap-4">
              <RouterLink to="/signup" className="w-full sm:w-auto px-10 py-5 bg-slate-900 text-white rounded-sm text-xs font-black hover:bg-slate-800 transition-all flex items-center justify-center gap-3 uppercase tracking-[0.2em]">
                Provision Workspace <ArrowRight size={18} strokeWidth={3} />
              </RouterLink>
              <a href="#features" className="w-full sm:w-auto px-10 py-5 bg-white text-slate-900 border border-slate-200 rounded-sm text-xs font-black hover:bg-slate-50 transition-all flex items-center justify-center gap-3 uppercase tracking-[0.2em]">
                View Specs
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Audit Transparency Strip */}
      <section className="py-20 bg-slate-50 border-y border-slate-200">
        <div className="max-w-[1400px] mx-auto px-8 grid grid-cols-1 md:grid-cols-4 gap-12">
          {[
            { label: 'Data Provenance', value: '100% Traceable', desc: 'Every field cites a specific document chunk.' },
            { label: 'Validation Cycle', value: 'Auto-RTS', desc: 'Real-time checks against regulatory standards.' },
            { label: 'Architecture', value: 'Multi-Tenant', desc: 'Strict organizational data isolation.' },
            { label: 'Audit Log', value: 'Immutable', desc: 'Hashed reviewer actions & edits.' },
          ].map((item, i) => (
            <div key={i} className="space-y-3">
              <div className="text-[10px] font-black text-slate-400 uppercase tracking-widest leading-none">{item.label}</div>
              <div className="text-xl font-black text-slate-900 tracking-tight uppercase leading-none">{item.value}</div>
              <div className="text-xs font-bold text-slate-500 font-sans leading-tight">{item.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Protocol Specs Section */}
      <section id="features" className="py-32 bg-white">
        <div className="max-w-[1400px] mx-auto px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-20">
            <div className="lg:col-span-4">
              <h2 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.3em] mb-6">01. ENGINE SPECS</h2>
              <h3 className="text-4xl font-black tracking-tighter text-slate-900 mb-8 leading-tight uppercase">BUILT FOR <br />VERIFICATION.</h3>
              <p className="text-slate-500 font-bold leading-relaxed font-sans">
                Clarix replaces the manually intensive "box-ticking" exercise with a structured data extraction protocol.
                We prioritize evidence density over conversational complexity.
              </p>
            </div>

            <motion.div
              className="lg:col-span-8 grid grid-cols-1 md:grid-cols-2 gap-px bg-slate-200 border border-slate-200"
              variants={containerVariants}
              initial="hidden"
              whileInView="visible"
              viewport={{ once: true }}
            >
              {FEATURES.map((feature, i) => (
                <motion.div key={i} variants={itemVariants} className="p-10 bg-white hover:bg-slate-50 transition-all duration-300">
                  <div className="w-10 h-10 bg-slate-900 rounded-sm flex items-center justify-center text-white mb-8">
                    {feature.icon}
                  </div>
                  <div className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-4">{feature.code}</div>
                  <h4 className="text-xl font-black text-slate-900 mb-4 tracking-tight uppercase">{feature.title}</h4>
                  <p className="text-slate-500 font-bold leading-relaxed font-sans text-sm">{feature.desc}</p>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </div>
      </section>

      {/* Integrated Workspace Preview (Deterministic View) */}
      <section id="audit" className="py-20 px-8">
        <div className="max-w-[1400px] mx-auto bg-slate-950 rounded-sm p-12 md:p-20 relative overflow-hidden">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div className="space-y-8">
              <h3 className="text-3xl font-black text-white tracking-tight leading-none uppercase">AUDIT-LAYER <br />PERSISTENCE.</h3>
              <p className="text-slate-400 font-bold font-sans leading-relaxed">
                The Clarix orchestrator prevents data leakage through strict tenant-scoping and immutable audit logs.
                Manage hundreds of reporting projects across multiple portfolios from a single, high-fidelity command center.
              </p>
              <ul className="space-y-4">
                {['DETERMINISTIC_CITATION_LOG', 'TENANT_OWNERSHIP_SYMMETRY', 'RTS_SCHEMA_ENFORCEMENT'].map((rule) => (
                  <li key={rule} className="flex items-center gap-3 text-[10px] font-black text-emerald-400 tracking-widest uppercase">
                    <CheckCircle2 size={14} /> {rule} :: OK
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-sm p-8 font-mono">
              <div className="flex items-center justify-between mb-8 pb-4 border-b border-white/10">
                <span className="text-[10px] text-white/40 uppercase tracking-widest">INGESTION_LOG_STREAM</span>
                <span className="text-[10px] text-indigo-400">ACTIVE:8000</span>
              </div>
              <div className="space-y-3">
                <div className="text-[11px] text-emerald-400">[0.12s] PARSING_PDF :: SUSTAINABILITY_REPORT_v1_25</div>
                <div className="text-[11px] text-slate-500">[0.45s] CHUNKING_COMPLETED :: 1500_BLOCKS</div>
                <div className="text-[11px] text-emerald-400">[0.88s] CITATION_MATCHED :: GHG_SCOPE_1 {"->"} PAGE_12</div>
                <div className="text-[11px] text-amber-500">[1.12s] VALIDATION_WARNING :: UNIT_MISMATCH_EXPECTED_CO2e</div>
                <div className="text-[11px] text-slate-300 group-hover:block transition-all mt-6 pt-4 border-t border-white/5">
                  ID: <span className="text-white">PROJECT_7f3d_INIT</span><br />
                  ORG: <span className="text-white">DEFAULT_TENANT_SECURE</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-40 px-8 text-center border-t border-slate-200 mt-20">
        <h2 className="text-4xl md:text-6xl font-black tracking-tighter text-slate-900 mb-12 leading-[0.9] uppercase">
          COMMENCE <br />REPORTING OPS.
        </h2>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-6">
          <RouterLink to="/signup" className="w-full sm:w-auto px-12 py-5 bg-slate-900 text-white rounded-sm text-xs font-black hover:bg-slate-800 transition-all uppercase tracking-[0.2em]">
            Initialize Now
          </RouterLink>
          <RouterLink to="/login" className="px-8 py-4 text-xs font-black text-slate-400 hover:text-slate-900 transition-all uppercase tracking-[0.2em] border-b-2 border-transparent hover:border-slate-900">
            Sign In to Existing Node
          </RouterLink>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-20 px-8 border-t border-slate-100 bg-slate-50">
        <div className="max-w-[1400px] mx-auto flex flex-col md:flex-row justify-between items-start gap-12">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-8 h-8 bg-slate-900 rounded-sm flex items-center justify-center text-white">
                <ShieldAlert size={16} strokeWidth={2.5} />
              </div>
              <span className="font-black text-xl tracking-tighter uppercase">Clarix</span>
            </div>
            <p className="text-[10px] font-bold text-slate-400 max-w-xs uppercase tracking-widest leading-relaxed">
              DETERMINISTIC COMPLIANCE INFRASTRUCTURE FOR ASSET MANAGERS AND CORPORATES.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-20">
            <div className="space-y-6">
              <h5 className="text-[10px] uppercase tracking-[0.3em] text-slate-300 font-black">INFRA</h5>
              <ul className="space-y-4">
                <li><a href="#" className="font-bold text-[10px] text-slate-400 hover:text-slate-900 transition-all tracking-widest uppercase">API.PROTO</a></li>
                <li><a href="#" className="font-bold text-[10px] text-slate-400 hover:text-slate-900 transition-all tracking-widest uppercase">DOCS.MD</a></li>
              </ul>
            </div>
            <div className="space-y-6">
              <h5 className="text-[10px] uppercase tracking-[0.3em] text-slate-300 font-black">NODE</h5>
              <ul className="space-y-4">
                <li><a href="#" className="font-bold text-[10px] text-slate-400 hover:text-slate-900 transition-all tracking-widest uppercase">UPTIME.SYS</a></li>
                <li><a href="#" className="font-bold text-[10px] text-slate-400 hover:text-slate-900 transition-all tracking-widest uppercase">SECURITY.LOG</a></li>
              </ul>
            </div>
          </div>
        </div>

        <div className="max-w-[1400px] mx-auto mt-20 pt-8 border-t border-slate-200 flex justify-between items-center">
          <p className="text-[9px] font-black text-slate-300 uppercase tracking-[0.4em]">© 2026 CLARIX COMPLIANCE ORCHESTRATOR. [REV_3.2]</p>
        </div>
      </footer>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&family=Inter:wght@400;700;900&display=swap');
        
        body {
          font-family: 'JetBrains Mono', monospace;
        }

        .font-sans {
          font-family: 'Inter', sans-serif;
        }
      `}</style>
    </div>
  );
}