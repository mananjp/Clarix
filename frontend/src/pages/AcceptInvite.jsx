import React, { useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { User, Lock, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import client from '../api/client';

const AcceptInvite = () => {
  const { token } = useParams();
  const navigate = useNavigate();

  const { currentUser } = useAuth();
  const [username, setUsername] = useState(currentUser?.username || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleAccept = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');

    try {
      await client.post('/invites/accept', { token, username, password });
      setNotice('Invite accepted. You can now log in with the password you set.');
      setTimeout(() => navigate('/login'), 1500);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to accept invite.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col gap-8 font-sans">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-slate-900 mb-2">Join your team</h2>
        <p className="text-slate-500 font-medium tracking-tight">Set your details to activate your account</p>
      </div>

      {error && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="p-4 bg-rose-50 border border-rose-100 rounded-2xl text-rose-600 text-sm font-semibold flex items-center gap-3"
        >
          <span>{error}</span>
        </motion.div>
      )}
      {notice && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="p-4 bg-emerald-50 border border-emerald-100 rounded-2xl text-emerald-700 text-sm font-semibold"
        >
          {notice}
        </motion.div>
      )}

      <form onSubmit={handleAccept} className="flex flex-col gap-5">
        <div>
          <label className="text-sm font-bold text-slate-700 ml-1">Your name</label>
          <div className="relative mt-1">
            <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" />
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-[20px] text-base focus:outline-none focus:border-slate-900 focus:bg-white"
              placeholder="Enter your name"
            />
          </div>
        </div>

        <div>
          <label className="text-sm font-bold text-slate-700 ml-1">Set a password</label>
          <div className="relative mt-1">
            <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-300" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full pl-12 pr-4 py-4 bg-slate-50 border border-slate-200 rounded-[20px] text-base focus:outline-none focus:border-slate-900 focus:bg-white"
              placeholder="Minimum 8 characters"
            />
          </div>
        </div>

        <motion.button
          whileTap={{ scale: 0.98 }}
          type="submit"
          disabled={isLoading}
          className="w-full py-5 bg-slate-900 text-white rounded-[20px] text-base font-bold hover:bg-slate-800 transition-all flex items-center justify-center gap-2 mt-2 disabled:opacity-50"
        >
          {isLoading ? <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin"></div> : <>Accept invite <ArrowRight size={20} /></>}
        </motion.button>
      </form>

      <div className="pt-6 border-t border-slate-50 text-center">
        <p className="text-sm font-semibold text-slate-400">
          Already have an account?{' '}
          <Link to="/login" className="text-slate-900 hover:underline font-bold ml-1">Sign in</Link>
        </p>
      </div>
    </div>
  );
};

export default AcceptInvite;