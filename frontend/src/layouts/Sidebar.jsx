import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Table, ClipboardCheck, History, Settings, X, ShieldAlert, LogOut, Package, Scale, ShieldCheck, LineChart } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import { useProjects } from '../context/ProjectContext';

const Sidebar = ({ isOpen, onClose }) => {
  const { logout, currentUser } = useAuth();
  const { selectedProjectId } = useProjects();

  const getPathWithProject = (to) => {
    if (!selectedProjectId || to === '/dashboard' || to === '/settings') return to;
    return `${to}?projectId=${selectedProjectId}`;
  };

  return (
    <>
      {/* Mobile Overlay */}
      <div
        className={`fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-30 transition-opacity lg:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={onClose}
      ></div>

      <aside
        className={`fixed lg:static inset-y-0 left-0 w-72 bg-white flex flex-col z-40 transition-transform duration-300 border-r border-slate-100 ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}
      >
        <div className="p-8 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-slate-900 rounded-xl flex items-center justify-center text-white shadow-xl shadow-slate-900/10">
              <ShieldAlert size={22} strokeWidth={2} />
            </div>
            <span className="font-bold text-2xl text-slate-900 tracking-tight">Clarix</span>
          </div>
          <button className="lg:hidden text-slate-400 hover:text-slate-900" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {[
            { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
            { to: '/matrix', icon: Table, label: 'Requirement Matrix' },
            { to: '/reviewer', icon: ClipboardCheck, label: 'Reviewer Desk' },
            { to: '/regulatory-impact', icon: Scale, label: 'Impact Simulator' },
            { to: '/auditor', icon: ShieldCheck, label: 'Auditor Portal' },
            { to: '/trends', icon: LineChart, label: 'Predictive Trends' },
            { to: '/audit', icon: History, label: 'Audit Trail' },
            { to: '/exports', icon: Package, label: 'Export Package' },
            { to: '/settings', icon: Settings, label: 'Settings' }
          ].map((item) => (
            <NavLink
              key={item.to}
              to={getPathWithProject(item.to)}
              onClick={onClose}
              className={({ isActive }) => `
                relative flex items-center gap-4 px-5 py-4 rounded-2xl transition-all duration-200 group
                ${isActive
                  ? 'bg-slate-900 text-white shadow-lg shadow-slate-900/10'
                  : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'}
              `}
            >
              {({ isActive }) => (
                <>
                  <item.icon size={20} className={`${isActive ? 'text-white' : 'text-slate-400 group-hover:text-slate-900'}`} />
                  <span className="text-sm font-bold tracking-tight">{item.label}</span>
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active"
                      className="absolute left-2 w-1.5 h-1.5 bg-white rounded-full"
                    />
                  )}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-100 mt-auto">
          <div className="bg-slate-50 p-5 rounded-2xl border border-slate-100 mb-2">
            <div className="text-xs font-bold text-slate-900 uppercase tracking-widest">{currentUser?.username || 'Guest Administrator'}</div>
            <div className="text-[10px] text-slate-400 mt-1 font-bold uppercase tracking-widest">{currentUser?.role || 'Reviewer Account'}</div>
          </div>

          <button
            onClick={logout}
            className="flex items-center justify-center gap-2 w-full py-4 bg-white border border-slate-100 rounded-2xl text-xs font-black text-slate-400 hover:text-rose-600 hover:border-rose-100 hover:bg-rose-50 transition-all uppercase tracking-widest"
          >
            <LogOut size={16} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
