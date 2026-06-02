  import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, Lock, LogIn } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to login. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 24 }}
      className="glass-card p-10 rounded-3xl w-full max-w-md relative overflow-hidden"
    >
      {/* Decorative blurred background blob */}
      <div className="absolute -top-24 -right-24 w-48 h-48 bg-primary-400 rounded-full blur-[80px] opacity-20 pointer-events-none"></div>
      
      <div className="text-center mb-8 relative z-10">
        <h2 className="text-3xl font-extrabold text-slate-900 tracking-tight">Welcome Back</h2>
        <p className="text-slate-500 font-medium mt-2">Sign in to your compliance workspace</p>
      </div>

      {error && (
        <motion.div 
          initial={{ opacity: 0, height: 0 }} 
          animate={{ opacity: 1, height: 'auto' }} 
          className="mb-6 p-4 rounded-xl bg-rose-50 border border-rose-100 text-rose-600 text-sm font-medium flex items-start gap-3"
        >
          <div className="mt-0.5">⚠️</div>
          <div>{error}</div>
        </motion.div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6 relative z-10">
        <div className="flex flex-col gap-2">
          <label className="text-sm font-bold text-slate-700">Email Address</label>
          <div className="relative">
            <Mail size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="form-input pl-11 py-3 text-base"
              placeholder="you@company.com"
            />
          </div>
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center">
            <label className="text-sm font-bold text-slate-700">Password</label>
            <a href="#" className="text-xs font-bold text-primary-600 hover:text-primary-700 transition-colors">Forgot Password?</a>
          </div>
          <div className="relative">
            <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="form-input pl-11 py-3 text-base tracking-widest"
              placeholder="••••••••"
            />
          </div>
        </div>

        <div className="flex items-center gap-3 mt-2">
          <input type="checkbox" id="remember" className="w-4 h-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500 cursor-pointer" />
          <label htmlFor="remember" className="text-sm font-medium text-slate-600 cursor-pointer select-none">Remember me for 30 days</label>
        </div>

        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          type="submit"
          disabled={isLoading}
          className="btn btn-primary w-full py-3.5 text-base shadow-primary-500/30 disabled:opacity-70 mt-2"
        >
          {isLoading ? (
            <svg className="animate-spin h-5 w-5 text-white mx-auto" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          ) : (
            <>
              <span className="font-bold">Sign In to Workspace</span>
            </>
          )}
        </motion.button>
      </form>

      <p className="mt-8 text-center text-sm font-medium text-slate-500 relative z-10">
        Don't have an account?{' '}
        <Link to="/signup" className="text-primary-600 hover:text-primary-700 font-bold ml-1 transition-colors">
          Create one now
        </Link>
      </p>
    </motion.div>
  );
};

export default Login;
