import { useState, useEffect } from 'react';
import { Database, Loader, Search, CheckCircle, XCircle, ShieldCheck, Percent, Filter } from 'lucide-react';
import { motion } from 'framer-motion';
import client from '../api/client';

/**
 * ESG Feed Coverage view (SFDR investee PAI data-availability).
 *
 * For a given investee ISIN, pulls the numeric PAI field codes debatable from
 * the configured third-party provider (Sustainalytics / MSCI / mock), then lets
 * the compliance officer fetch metrics and visually compare "requested" vs
 * "returned" to understand PAI data coverage — the core SFDR data-availability
 * gap for asset managers.
 */
const EsgFeedCoverage = () => {
  const [fields, setFields] = useState([]);
  const [framework, setFramework] = useState('SFDR');
  const [isin, setIsin] = useState('');
  const [result, setResult] = useState(null);
  const [isLoadingFields, setIsLoadingFields] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [error, setError] = useState('');

  const loadFields = async (fw) => {
    setIsLoadingFields(true);
    try {
      const res = await client.get(`/esg-feed/fields?framework=${fw}`);
      setFields(res.data?.fields || []);
    } catch (err) {
      console.error('Failed to load ESg feed fields', err);
      setFields([]);
    } finally {
      setIsLoadingFields(false);
    }
  };

  useEffect(() => {
    loadFields(framework);
  }, [framework]);

  const handleFetch = async () => {
    if (!isin.trim()) { setError('Enter an investee ISIN.'); return; }
    setError('');
    setIsFetching(true);
    setResult(null);
    try {
      const res = await client.post('/esg-feed/company/fetch', {
        isin: isin.trim().toUpperCase(),
        framework,
        requested_fields: fields,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'ESG feed fetch failed.');
    } finally {
      setIsFetching(false);
    }
  };

  const requestedCount = fields.length;
  const returnedCount = result ? Object.keys(result.metrics || {}).length : 0;
  const pct = result?.coverage ?? 0;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col gap-6 w-full">
      {/* Header */}
      <div className="glass-card p-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">SFDR Data Availability</span>
          <h2 className="text-2xl font-black text-slate-900 tracking-tight mt-1 flex items-center gap-3">
            ESG Feed Coverage
            <span className="badge badge-success flex items-center gap-1.5 text-xs px-3 py-1"><ShieldCheck size={14} /> PAI</span>
          </h2>
          <p className="text-sm text-slate-500 font-medium mt-1">
            Compare requested PAI indicators against the investee data returned by the third-party feed.
          </p>
        </div>
        <select
          className="form-input bg-white min-w-[200px] font-black text-xs uppercase tracking-widest text-slate-700"
          value={framework}
          onChange={(e) => setFramework(e.target.value)}
        >
          <option value="SFDR">SFDR</option>
          <option value="CSRD">CSRD</option>
        </select>
      </div>

      {/* Lookup bar */}
      <div className="glass-card p-6">
        <div className="flex flex-col md:flex-row gap-4 items-end">
          <div className="flex-1">
            <label className="text-[11px] font-black text-slate-400 uppercase tracking-widest mb-2 block">Investee Company ISIN</label>
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                className="form-input pl-9 bg-white"
                placeholder="e.g. US1234567890"
                value={isin}
                onChange={(e) => setIsin(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleFetch()}
              />
            </div>
          </div>
          <motion.button
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            onClick={handleFetch}
            disabled={isFetching}
            className="btn btn-primary disabled:opacity-70 flex items-center gap-2"
          >
            {isFetching ? <Loader size={16} className="animate-spin" /> : <Database size={16} />}
            {isFetching ? 'Fetching...' : 'Fetch Coverage'}
          </motion.button>
        </div>
        {error && <p className="text-sm font-bold text-rose-600 mt-3">{error}</p>}
      </div>

      {/* Field list */}
      <div className="glass-card p-6 flex flex-col gap-4">
        <div className="flex items-center gap-2 border-b border-slate-100 pb-4">
          <Filter size={16} className="text-primary-600" />
          <h3 className="font-bold text-slate-800">Requestable PAI Indicators ({requestedCount})</h3>
          {isLoadingFields && <Loader size={14} className="animate-spin text-slate-400" />}
        </div>

        {fields.length === 0 && !isLoadingFields ? (
          <p className="text-sm text-slate-400 font-bold py-6 text-center">No numeric PAI fields found for framework.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {fields.map(code => (
              <span key={code} className="inline-flex items-center gap-1.5 text-[11px] font-mono font-bold bg-slate-50 border border-slate-100 text-slate-600 px-2 py-1 rounded-lg">
                {code}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Coverage result */}
      {result && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 flex flex-col gap-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 border-b border-slate-100 pb-5">
            <div>
              <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">ISIN {result.isin} • Provider {result.provider} • {result.framework}</p>
              <div className="flex items-center gap-2 mt-2">
                <Percent size={16} className="text-primary-600" />
                <span className="text-2xl font-black text-slate-900">{pct}%</span>
                <span className="text-sm text-slate-500 font-bold">data coverage</span>
              </div>
            </div>
            <div className="text-right">
              <span className="text-xs font-black text-slate-400 uppercase tracking-widest">Returned</span>
              <p className="text-2xl font-black text-slate-900">{returnedCount}/{requestedCount}</p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <h4 className="text-[11px] font-black text-emerald-600 uppercase tracking-widest mb-3 flex items-center gap-2"><CheckCircle size={14} /> Returned metrics</h4>
              <div className="flex flex-col gap-2">
                {Object.keys(result.metrics || {}).map(code => (
                  <div key={code} className="flex items-center justify-between p-3 bg-emerald-50/40 border border-emerald-100 rounded-xl">
                    <code className="text-[11px] font-mono font-bold text-slate-700">{code}</code>
                    <span className="text-sm font-black text-slate-900">
                      {result.metrics[code].value}
                      <span className="text-[10px] font-bold text-slate-400 ml-1">{result.metrics[code].unit}</span>
                    </span>
                  </div>
                ))}
                {returnedCount === 0 && <p className="text-sm text-slate-400 font-bold py-3">No metrics returned for this ISIN.</p>}
              </div>
            </div>

            <div>
              <h4 className="text-[11px] font-black text-rose-500 uppercase tracking-widest mb-3 flex items-center gap-2"><XCircle size={14} /> Coverage gaps</h4>
              <div className="flex flex-col gap-2">
                {fields.filter(code => !(code in (result.metrics || {}))).map(code => (
                  <div key={code} className="flex items-center justify-between p-3 bg-slate-50 border border-slate-100 rounded-xl">
                    <code className="text-[11px] font-mono font-bold text-slate-500">{code}</code>
                    <span className="text-[10px] font-black text-slate-400 uppercase">no data</span>
                  </div>
                ))}
                {returnedCount === requestedCount && <p className="text-sm text-emerald-600 font-bold py-3">Full coverage — no gaps.</p>}
              </div>
            </div>
          </div>
        </motion.div>
      )}

      {!result && (
        <div className="glass-card p-10 flex flex-col items-center justify-center text-center">
          <Database size={40} className="text-slate-200 mb-4" />
          <p className="text-slate-400 font-bold">Fetch coverage for an investee ISIN to see PAI data availability.</p>
          <p className="text-xs text-slate-300 font-medium mt-1">Useful to identify which PAI indicators need manual / uploaded-document evidence.</p>
        </div>
      )}
    </motion.div>
  );
};

export default EsgFeedCoverage;