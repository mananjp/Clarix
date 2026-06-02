import React from 'react';
import { Outlet } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { motion } from 'framer-motion';

const AuthLayout = () => {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background relative items-center justify-center">
      {/* Decorative background gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-primary-200/40 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-accent-indigo/10 rounded-full blur-[150px] pointer-events-none"></div>

      <div className="w-full max-w-md p-6 relative z-10 flex flex-col gap-6">
        <motion.div 
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col items-center gap-3"
        >
          <div className="w-14 h-14 bg-gradient-to-br from-primary-600 to-accent-indigo rounded-2xl flex items-center justify-center text-white shadow-xl shadow-primary-500/30">
            <ShieldAlert size={28} strokeWidth={2.5} />
          </div>
          <span className="font-extrabold text-2xl text-slate-800 tracking-tight">SFDR<span className="text-primary-600 font-black">.</span>AI</span>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.1, type: "spring", stiffness: 300, damping: 25 }}
        >
          <Outlet />
        </motion.div>
      </div>
    </div>
  );
};

export default AuthLayout;
