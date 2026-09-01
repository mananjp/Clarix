import React, { useState, useEffect, useCallback } from 'react';
import { Users, UserPlus, Copy, Check, Mail, Shield, MailCheck } from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuth } from '../context/AuthContext';
import client from '../api/client';

const ROLES = [
  { value: 'Administrator', label: 'Administrator' },
  { value: 'ComplianceOfficer', label: 'Compliance Officer' },
  { value: 'Reviewer', label: 'Reviewer' },
  { value: 'Auditor', label: 'Auditor' },
];

const Team = () => {
  const { currentUser } = useAuth();
  const isAdmin = currentUser?.role === 'SuperAdmin' || currentUser?.role === 'Administrator';

  const [users, setUsers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('Reviewer');
  const [copied, setCopied] = useState(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [u, i] = await Promise.all([
        client.get('/users'),
        currentUser?.organization_id ? client.get(`/organizations/${currentUser.organization_id}/invites`) : Promise.resolve({ data: [] }),
      ]);
      setUsers(u.data || []);
      setInvites(i.data || []);
    } catch (e) {
      setError('Could not load team data.');
    }
  }, [currentUser?.organization_id]);

  useEffect(() => {
    if (isAdmin) loadData();
  }, [isAdmin, loadData]);

  const handleInvite = async (e) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const resp = await client.post(`/organizations/${currentUser.organization_id}/invites`, {
        email,
        role,
      });
      setInvites((prev) => [...prev, resp.data]);
      setEmail('');
      setNotice('Invite created. Share the link below with your teammate.');
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create invite.');
    } finally {
      setLoading(false);
    }
  };

  const inviteUrl = (invite) =>
    `${window.location.origin}/invite/${invite.token}`;

  const copyLink = (invite) => {
    const url = inviteUrl(invite);
    navigator.clipboard?.writeText(url);
    setCopied(invite.id);
    setTimeout(() => setCopied(null), 2000);
  };

  return (
    <div className="max-w-5xl mx-auto px-6 py-10 font-sans">
      <div className="flex items-center gap-3 mb-8">
        <Users size={22} className="text-slate-900" />
        <h1 className="text-2xl font-bold text-slate-900">Team</h1>
      </div>

      {!isAdmin ? (
        <div className="p-6 bg-slate-50 border border-slate-100 rounded-2xl text-slate-500 text-sm">
          Only an Administrator or Super Admin can manage team invites.
        </div>
      ) : (
        <>
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white border border-slate-100 rounded-[24px] p-6 mb-8 shadow-sm"
          >
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <UserPlus size={18} /> Invite a teammate
            </h2>

            {error && <div className="mb-4 p-3 bg-rose-50 border border-rose-100 rounded-xl text-rose-600 text-sm font-semibold">{error}</div>}
            {notice && <div className="mb-4 p-3 bg-emerald-50 border border-emerald-100 rounded-xl text-emerald-700 text-sm font-semibold">{notice}</div>}

            <form onSubmit={handleInvite} className="flex flex-col md:flex-row gap-3">
              <div className="flex-1">
                <label className="text-xs font-bold text-slate-500 uppercase tracking-widest ml-1">Email</label>
                <div className="relative mt-1">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-300" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="teammate@company.com"
                    className="w-full pl-9 pr-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:border-slate-900 focus:bg-white"
                  />
                </div>
              </div>
              <div>
                <label className="text-xs font-bold text-slate-500 uppercase tracking-widest ml-1">Role</label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="mt-1 w-full md:w-auto px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 focus:outline-none focus:border-slate-900 focus:bg-white"
                >
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </div>
              <div className="md:self-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="w-full md:w-auto px-6 py-3 bg-slate-900 text-white rounded-xl text-sm font-bold hover:bg-slate-800 flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {loading ? 'Sending…' : 'Send invite'}
                </button>
              </div>
            </form>

            {invites.length > 0 && (
              <div className="mt-6">
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-2">
                  <MailCheck size={14} /> Pending invites
                </h3>
                <div className="space-y-2">
                  {invites.map((inv) => (
                    <div key={inv.id} className="flex items-center justify-between gap-3 p-3 bg-slate-50 rounded-xl text-sm">
                      <div>
                        <div className="font-bold text-slate-800">{inv.email}</div>
                        <div className="text-xs text-slate-400 font-semibold">{inv.role}</div>
                      </div>
                      <button
                        onClick={() => copyLink(inv)}
                        className="flex items-center gap-1.5 px-3 py-2 bg-white border border-slate-200 rounded-lg text-xs font-bold text-slate-600 hover:text-slate-900"
                      >
                        {copied === inv.id ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                        {copied === inv.id ? 'Copied' : 'Copy link'}
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>

          <div className="bg-white border border-slate-100 rounded-[24px] p-6 shadow-sm">
            <h2 className="text-lg font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Shield size={18} /> Members
            </h2>
            <div className="divide-y divide-slate-50">
              {users.map((u) => (
                <div key={u.id} className="flex items-center justify-between py-3">
                  <div>
                    <div className="font-bold text-slate-800 text-sm">{u.username}</div>
                    <div className="text-xs text-slate-400">{u.email}</div>
                  </div>
                  <span className="text-xs font-bold px-3 py-1 rounded-full bg-slate-100 text-slate-600">{u.role}</span>
                </div>
              ))}
              {users.length === 0 && <div className="py-4 text-sm text-slate-400">No members yet.</div>}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default Team;