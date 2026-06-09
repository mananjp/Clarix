import React from 'react';
import { Outlet } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { motion } from 'framer-motion';

const AuthLayout = () => {
  return (
    <div className="min-h-screen w-screen overflow-y-auto bg-slate-50 font-sans text-slate-900 flex flex-col items-center justify-center p-6">
      <div className="w-full max-w-md flex flex-col gap-10">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="flex flex-col items-center gap-4"
        >
          <div className="w-14 h-14 bg-slate-900 rounded-2xl flex items-center justify-center text-white shadow-2xl shadow-slate-950/20">
            <ShieldAlert size={28} strokeWidth={2} />
          </div>
          <h1 className="text-3xl font-black tracking-tight">Clarix</h1>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1, duration: 0.4 }}
          className="bg-white rounded-[32px] p-10 shadow-xl shadow-slate-200/50 border border-slate-100"
        >
          <Outlet />
        </motion.div>

        <div className="text-center">
          <p className="text-sm font-medium text-slate-400">© 2026 Clarix Compliance platform</p>
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800;900&display=swap');
        body { font-family: 'Outfit', sans-serif; }
      `}</style>
    </div>
  );
};

export default AuthLayout;
