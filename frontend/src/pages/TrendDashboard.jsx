import React, { useState, useEffect } from 'react';
import { LineChart as ChartIcon, Sliders, Sparkles, CheckCircle, AlertTriangle, HelpCircle, Loader, RefreshCw } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import client from '../api/client';
import { useProjects } from '../context/ProjectContext';

const BRSR_METRICS = [
  { code: 'BRSR_GHG_SCOPE1', label: 'Scope 1 GHG Emissions', unit: 'tCO2e' },
  { code: 'BRSR_GHG_SCOPE2', label: 'Scope 2 GHG Emissions', unit: 'tCO2e' },
  { code: 'BRSR_GHG_SCOPE3', label: 'Scope 3 GHG Emissions', unit: 'tCO2e' },
  { code: 'BRSR_ENERGY_CONSUMPTION', label: 'Energy Consumption', unit: 'kWh' },
  { code: 'BRSR_WATER_WITHDRAWAL', label: 'Water Withdrawal', unit: 'kL' },
  { code: 'BRSR_WASTE_GENERATED', label: 'Waste Generated', unit: 'tonnes' }
];

const TrendDashboard = () => {
  const { projects } = useProjects();
  const [selectedOrgId, setSelectedOrgId] = useState('verify_org');
  const [activeMetricCode, setActiveMetricCode] = useState(BRSR_METRICS[0].code);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState({ status: 'insufficient_data' });
  const [scenarioForecast, setScenarioForecast] = useState(null);
  const [narrative, setNarrative] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isNarrativeLoading, setIsNarrativeLoading] = useState(false);

  // Intervention inputs
  const [effectType, setEffectType] = useState('relative_reduction');
  const [effectMagnitude, setEffectMagnitude] = useState(0.20); // 20%
  const [applicableFromYear, setApplicableFromYear] = useState(2026);

  // Targets inputs
  const [targetValue, setTargetValue] = useState('');
  const [targetYear, setTargetYear] = useState('2026');

  const activeMetric = BRSR_METRICS.find(m => m.code === activeMetricCode);

  // Auto-detect organization ID from active project
  useEffect(() => {
    if (projects.length > 0 && projects[0].organization_id) {
      setSelectedOrgId(projects[0].organization_id);
    }
  }, [projects]);

  // Fetch trend data
  const fetchTrendData = async () => {
    if (!selectedOrgId) return;
    setIsLoading(true);
    try {
      const targetValNum = targetValue !== '' ? parseFloat(targetValue) : null;
      const targetYrNum = targetYear !== '' ? parseInt(targetYear) : null;

      let params = { horizon: 1 };
      if (targetValNum !== null) params.target_value = targetValNum;
      if (targetYrNum !== null) params.target_year = targetYrNum;

      const res = await client.get(`/organizations/${selectedOrgId}/trends/${activeMetricCode}`, { params });
      setHistory(res.data.history || []);
      setForecast(res.data.forecast || { status: 'insufficient_data' });
      setNarrative(res.data.narrative || '');
      setScenarioForecast(null); // Reset custom scenario path
    } catch (err) {
      console.error("Failed to fetch trend data", err);
      setHistory([]);
      setForecast({ status: 'insufficient_data' });
      setNarrative('Error loading trends.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTrendData();
  }, [selectedOrgId, activeMetricCode]);

  // Run scenario simulation
  const handleSimulateScenario = async () => {
    if (!selectedOrgId || forecast.status !== 'ok') return;
    setIsLoading(true);
    try {
      const res = await client.post(`/organizations/${selectedOrgId}/scenarios`, {
        field_code: activeMetricCode,
        effect_type: effectType,
        effect_magnitude: parseFloat(effectMagnitude),
        applicable_from_year: parseInt(applicableFromYear)
      });
      setScenarioForecast(res.data.scenario_forecast);
    } catch (err) {
      console.error("Failed to simulate scenario", err);
      alert("Failed to run scenario simulation.");
    } finally {
      setIsLoading(false);
    }
  };

  // Re-generate AI Narrative Insight
  const handleRegenerateNarrative = async () => {
    if (!selectedOrgId || forecast.status !== 'ok') return;
    setIsNarrativeLoading(true);
    try {
      const targetValNum = targetValue !== '' ? parseFloat(targetValue) : null;
      const targetYrNum = targetYear !== '' ? parseInt(targetYear) : null;

      let params = {};
      if (targetValNum !== null) params.target_value = targetValNum;
      if (targetYrNum !== null) params.target_year = targetYrNum;

      const res = await client.get(`/companies/${selectedOrgId}/trend-narrative/${activeMetricCode}`, { params });
      setNarrative(res.data.narrative);
    } catch (err) {
      console.error("Failed to regenerate narrative", err);
    } finally {
      setIsNarrativeLoading(false);
    }
  };

  // SVG Line Chart Logic
  const renderSvgChart = () => {
    if (history.length < 2) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
          <ChartIcon size={40} className="stroke-1" />
          <p className="text-sm font-semibold">Insufficient Data for Trend Analysis</p>
          <p className="text-xs text-slate-500 text-center max-w-xs">Please finalize and extract snapshots for at least two reporting years.</p>
        </div>
      );
    }

    const margin = { top: 20, right: 40, bottom: 40, left: 60 };
    const width = 600;
    const height = 300;
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;

    // Compile all years and values
    const years = history.map(h => h.year);
    const values = history.map(h => h.value);

    let allYears = [...years];
    let allValues = [...values];

    if (forecast.status === 'ok') {
      allYears.push(forecast.target_year);
      allValues.push(forecast.forecast_value);
      allValues.push(forecast.lower_bound_80pct);
      allValues.push(forecast.upper_bound_80pct);
    }

    if (scenarioForecast) {
      allValues.push(scenarioForecast.scenario_forecast_value);
    }

    if (targetValue !== '' && !isNaN(parseFloat(targetValue))) {
      allValues.push(parseFloat(targetValue));
      if (targetYear !== '') allYears.push(parseInt(targetYear));
    }

    const minYear = Math.min(...allYears);
    const maxYear = Math.max(...allYears);
    const minValue = Math.min(...allValues);
    const maxValue = Math.max(...allValues);

    const yearRange = maxYear - minYear || 1;
    const valuePad = (maxValue - minValue) * 0.1 || 10;
    const valueMin = Math.max(0, minValue - valuePad);
    const valueMax = maxValue + valuePad;
    const valueRange = valueMax - valueMin || 1;

    // Coordinate conversion helpers
    const getX = (year) => margin.left + ((year - minYear) / yearRange) * plotWidth;
    const getY = (val) => margin.top + plotHeight - ((val - valueMin) / valueRange) * plotHeight;

    // Build historical path
    const historyCoords = history.map(h => ({ x: getX(h.year), y: getY(h.value), ...h }));
    const historyPath = historyCoords.reduce((path, p, i) => i === 0 ? `M ${p.x} ${p.y}` : `${path} L ${p.x} ${p.y}`, '');

    // Last historical point
    const lastHist = historyCoords[historyCoords.length - 1];

    // Forecast bounds
    let forecastBaseCoord = null;
    let forecastUpperCoord = null;
    let forecastLowerCoord = null;
    let confidencePoly = '';

    if (forecast.status === 'ok') {
      forecastBaseCoord = { x: getX(forecast.target_year), y: getY(forecast.forecast_value) };
      forecastUpperCoord = { x: getX(forecast.target_year), y: getY(forecast.upper_bound_80pct) };
      forecastLowerCoord = { x: getX(forecast.target_year), y: getY(forecast.lower_bound_80pct) };

      // Cone shape connecting last historical to bounds
      confidencePoly = `M ${lastHist.x} ${lastHist.y} L ${forecastUpperCoord.x} ${forecastUpperCoord.y} L ${forecastLowerCoord.x} ${forecastLowerCoord.y} Z`;
    }

    // Scenario point
    let scenarioCoord = null;
    if (scenarioForecast) {
      scenarioCoord = { x: getX(forecast.target_year), y: getY(scenarioForecast.scenario_forecast_value) };
    }

    // Target reference line
    let targetRef = null;
    if (targetValue !== '' && !isNaN(parseFloat(targetValue))) {
      const tVal = parseFloat(targetValue);
      const tYr = targetYear !== '' ? parseInt(targetYear) : minYear;
      targetRef = { x: getX(tYr), y: getY(tVal), value: tVal, year: tYr };
    }

    // Generate Y-axis grid ticks (4 subdivisions)
    const yTicks = [];
    for (let i = 0; i <= 4; i++) {
      const val = valueMin + (valueRange / 4) * i;
      yTicks.push({ value: val, y: getY(val) });
    }

    // Generate X-axis grid ticks (all years)
    const xTicks = [];
    const uniqueYears = Array.from(new Set(allYears)).sort((a, b) => a - b);
    uniqueYears.forEach(yr => {
      xTicks.push({ year: yr, x: getX(yr) });
    });

    return (
      <svg className="w-full h-full" viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <linearGradient id="chartGlow" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.15" />
            <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.0" />
          </linearGradient>
        </defs>

        {/* Grid lines */}
        {yTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={margin.left}
              y1={t.y}
              x2={width - margin.right}
              y2={t.y}
              stroke="#e2e8f0"
              strokeWidth="1"
              strokeDasharray="4 4"
            />
            <text
              x={margin.left - 8}
              y={t.y + 4}
              textAnchor="end"
              className="text-[10px] font-bold text-slate-400 font-mono"
            >
              {Math.round(t.value).toLocaleString()}
            </text>
          </g>
        ))}

        {xTicks.map((t, i) => (
          <g key={i}>
            <line
              x1={t.x}
              y1={margin.top}
              x2={t.x}
              y2={height - margin.bottom}
              stroke="#e2e8f0"
              strokeWidth="1"
              strokeDasharray="4 4"
            />
            <text
              x={t.x}
              y={height - margin.bottom + 18}
              textAnchor="middle"
              className="text-[10px] font-bold text-slate-500 font-mono"
            >
              {t.year}
            </text>
          </g>
        ))}

        {/* Confidence Band Area */}
        {forecast.status === 'ok' && (
          <path
            d={confidencePoly}
            fill="#818cf8"
            fillOpacity="0.1"
            className="transition-all duration-300"
          />
        )}

        {/* Historical Area Fill */}
        {historyCoords.length > 0 && (
          <path
            d={`${historyPath} L ${lastHist.x} ${getY(valueMin)} L ${historyCoords[0].x} ${getY(valueMin)} Z`}
            fill="url(#chartGlow)"
          />
        )}

        {/* Historical Line */}
        <path
          d={historyPath}
          fill="none"
          stroke="#4f46e5"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Historical Dots */}
        {historyCoords.map((p, i) => (
          <circle
            key={i}
            cx={p.x}
            cy={p.y}
            r="5"
            fill="#ffffff"
            stroke="#4f46e5"
            strokeWidth="2.5"
            className="hover:r-7 cursor-pointer transition-all"
          />
        ))}

        {/* Target Reference Line */}
        {targetRef && (
          <g>
            <line
              x1={margin.left}
              y1={targetRef.y}
              x2={width - margin.right}
              y2={targetRef.y}
              stroke="#ef4444"
              strokeWidth="2"
              strokeDasharray="5 5"
            />
            <circle
              cx={targetRef.x}
              cy={targetRef.y}
              r="6"
              fill="#ef4444"
            />
            <text
              x={targetRef.x + 8}
              y={targetRef.y - 6}
              className="text-[9px] font-extrabold fill-rose-600 bg-white"
            >
              SBTi Target ({targetRef.value})
            </text>
          </g>
        )}

        {/* Forecast Baseline Line */}
        {forecast.status === 'ok' && (
          <>
            <line
              x1={lastHist.x}
              y1={lastHist.y}
              x2={forecastBaseCoord.x}
              y2={forecastBaseCoord.y}
              stroke="#f59e0b"
              strokeWidth="2.5"
              strokeDasharray="6 4"
            />
            <circle
              cx={forecastBaseCoord.x}
              cy={forecastBaseCoord.y}
              r="5"
              fill="#f59e0b"
            />
            <text
              x={forecastBaseCoord.x}
              y={forecastBaseCoord.y - 10}
              textAnchor="middle"
              className="text-[9px] font-bold fill-amber-700 bg-white"
            >
              Proj: {Math.round(forecast.forecast_value).toLocaleString()}
            </text>
          </>
        )}

        {/* Scenario Line */}
        {scenarioForecast && scenarioCoord && (
          <>
            <line
              x1={lastHist.x}
              y1={lastHist.y}
              x2={scenarioCoord.x}
              y2={scenarioCoord.y}
              stroke="#10b981"
              strokeWidth="2.5"
              strokeDasharray="6 4"
            />
            <circle
              cx={scenarioCoord.x}
              cy={scenarioCoord.y}
              r="5"
              fill="#10b981"
            />
            <text
              x={scenarioCoord.x}
              y={scenarioCoord.y + 16}
              textAnchor="middle"
              className="text-[9px] font-bold fill-emerald-700 bg-white"
            >
              Scenario: {Math.round(scenarioForecast.scenario_forecast_value).toLocaleString()}
            </text>
          </>
        )}
      </svg>
    );
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex flex-col gap-6 w-full max-w-6xl mx-auto"
    >
      {/* Top Selector pills */}
      <div className="glass-card p-6 flex flex-col gap-4 shadow-sm">
        <div>
          <span className="text-xs font-black text-primary-600 uppercase tracking-wider">Predictive Transition Analytics</span>
          <h1 className="text-3xl font-bold text-slate-800 tracking-tight mt-1">BRSR Core Performance Forecasts</h1>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          {BRSR_METRICS.map(m => (
            <button
              key={m.code}
              onClick={() => setActiveMetricCode(m.code)}
              className={`px-4 py-2.5 rounded-xl text-xs font-bold transition-all ${activeMetricCode === m.code
                  ? 'bg-primary-600 text-white shadow-md shadow-primary-500/20'
                  : 'bg-slate-50 text-slate-600 hover:bg-slate-100 hover:text-slate-800'
                }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Left Column: Simulation Panels */}
        <div className="flex flex-col gap-6 lg:col-span-1">

          {/* SBTi Target Settings */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 text-base">
              <Sliders size={18} className="text-rose-500" />
              SBTi / Carbon Targets
            </h3>

            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">Target Value ({activeMetric?.unit})</label>
                <input
                  type="number"
                  placeholder="Set target figure..."
                  value={targetValue}
                  onChange={(e) => setTargetValue(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">Target Year</label>
                <select
                  value={targetYear}
                  onChange={(e) => setTargetYear(e.target.value)}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2"
                >
                  <option value="2026">2026</option>
                  <option value="2027">2027</option>
                  <option value="2028">2028</option>
                  <option value="2030">2030</option>
                </select>
              </div>

              <button
                onClick={fetchTrendData}
                className="btn btn-secondary w-full border-none bg-slate-100 hover:bg-slate-200/80 font-bold text-xs py-2 mt-2"
              >
                Apply Target
              </button>
            </div>
          </div>

          {/* Intervention Simulation Controls */}
          <div className="glass-card p-6 flex flex-col gap-4">
            <h3 className="font-bold text-slate-800 flex items-center gap-2 text-base">
              <Sliders size={18} className="text-primary-500" />
              Reduction Interventions
            </h3>

            <div className="flex flex-col gap-4">
              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">Intervention Type</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setEffectType('relative_reduction')}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold border transition-all ${effectType === 'relative_reduction'
                        ? 'border-primary-500 text-primary-700 bg-primary-50/50'
                        : 'border-slate-200 text-slate-600 bg-white'
                      }`}
                  >
                    Relative (%)
                  </button>
                  <button
                    onClick={() => setEffectType('absolute_reduction')}
                    className={`flex-1 py-1.5 rounded-lg text-xs font-bold border transition-all ${effectType === 'absolute_reduction'
                        ? 'border-primary-500 text-primary-700 bg-primary-50/50'
                        : 'border-slate-200 text-slate-600 bg-white'
                      }`}
                  >
                    Absolute
                  </button>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-500 flex justify-between mb-1">
                  <span>Reduction Magnitude</span>
                  <span className="font-bold text-primary-600">
                    {effectType === 'relative_reduction'
                      ? `${Math.round(effectMagnitude * 100)}%`
                      : `${effectMagnitude} ${activeMetric?.unit}`}
                  </span>
                </label>
                <input
                  type="range"
                  min="0.0"
                  max={effectType === 'relative_reduction' ? '1.0' : '50000'}
                  step={effectType === 'relative_reduction' ? '0.05' : '100'}
                  value={effectMagnitude}
                  onChange={(e) => setEffectMagnitude(parseFloat(e.target.value))}
                  className="w-full accent-primary-600"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-500 block mb-1">Applicable From Year</label>
                <select
                  value={applicableFromYear}
                  onChange={(e) => setApplicableFromYear(parseInt(e.target.value))}
                  className="w-full px-3 py-2 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2"
                >
                  <option value="2026">2026</option>
                  <option value="2027">2027</option>
                  <option value="2028">2028</option>
                </select>
              </div>

              <button
                onClick={handleSimulateScenario}
                disabled={forecast.status !== 'ok' || isLoading}
                className="btn btn-primary w-full py-2.5 font-bold shadow-lg shadow-primary-500/20"
              >
                {isLoading ? <Loader size={16} className="animate-spin mr-2" /> : null}
                <span>Simulate Scenario</span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Columns: Chart & Insights */}
        <div className="flex flex-col gap-6 lg:col-span-2">

          {/* Main Forecast Chart */}
          <div className="glass-card p-6 flex flex-col gap-6 h-[400px]">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <div>
                <h3 className="font-bold text-lg text-slate-800">{activeMetric?.label} Projections</h3>
                <p className="text-xs text-slate-400 mt-0.5 uppercase tracking-wide">Historical, Forecast Baseline & Custom Interventions</p>
              </div>
              <span className="bg-slate-100 px-3 py-1 rounded-full text-xs font-bold text-slate-600">
                Unit: {activeMetric?.unit}
              </span>
            </div>

            <div className="flex-1 min-h-0 relative">
              {isLoading ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
                  <Loader className="animate-spin text-primary-600" size={32} />
                  <span className="font-bold text-sm">Recalculating projection models...</span>
                </div>
              ) : (
                renderSvgChart()
              )}
            </div>
          </div>

          {/* AI Narrative Insight Card */}
          {forecast.status === 'ok' && (
            <div className="glass-card p-6 bg-gradient-to-br from-indigo-50/20 to-purple-50/20 border-indigo-100/50 flex flex-col gap-4 relative overflow-hidden">
              {/* Highlight background elements */}
              <div className="absolute right-0 top-0 w-32 h-32 bg-primary-200/10 rounded-full filter blur-2xl"></div>

              <div className="flex justify-between items-center">
                <h4 className="font-bold text-slate-800 flex items-center gap-2">
                  <Sparkles size={16} className="text-primary-600" />
                  AI Predictive Insight
                </h4>
                <button
                  onClick={handleRegenerateNarrative}
                  disabled={isNarrativeLoading}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100/50 transition-colors"
                  title="Regenerate Narrative"
                >
                  <RefreshCw size={14} className={isNarrativeLoading ? 'animate-spin' : ''} />
                </button>
              </div>

              {isNarrativeLoading ? (
                <div className="flex items-center gap-3 text-slate-500 py-4">
                  <Loader size={16} className="animate-spin text-primary-600" />
                  <span className="text-xs font-bold">Synthesizing narrative analysis...</span>
                </div>
              ) : (
                <p className="text-sm text-slate-700 leading-relaxed font-medium">
                  {narrative}
                </p>
              )}
            </div>
          )}

          {/* SBTi Target Attainment Panel */}
          {targetValue !== '' && forecast.status === 'ok' && (
            <div className="glass-card p-6">
              <h4 className="font-bold text-slate-800 mb-3 flex items-center gap-2">
                <CheckCircle size={18} className="text-emerald-500" />
                SBTi Target Compliance Progress
              </h4>

              {(() => {
                const projVal = forecast.forecast_value;
                const tVal = parseFloat(targetValue);
                const gap = projVal - tVal;

                const isMet = gap <= 0;
                let scenarioMet = false;
                let scenarioGap = 0;
                if (scenarioForecast) {
                  scenarioGap = scenarioForecast.scenario_forecast_value - tVal;
                  scenarioMet = scenarioGap <= 0;
                }

                return (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-3 bg-slate-50 p-4 rounded-xl border border-slate-100">
                      {isMet ? (
                        <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg">
                          <CheckCircle size={20} />
                        </div>
                      ) : (
                        <div className="p-2 bg-rose-100 text-rose-700 rounded-lg">
                          <AlertTriangle size={20} />
                        </div>
                      )}
                      <div>
                        <div className="text-sm font-bold text-slate-800">
                          {isMet
                            ? "Target Achieved Under Baseline Forecast!"
                            : `Target Violation Warning: Projected shortfall of ${Math.round(gap).toLocaleString()} ${activeMetric?.unit}`}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                          {isMet
                            ? "The current trajectory successfully hits the declared ESG targets."
                            : "Additional decarbonization interventions are required to meet the carbon limit."}
                        </div>
                      </div>
                    </div>

                    {scenarioForecast && (
                      <div className="flex items-center gap-3 bg-emerald-50/50 p-4 rounded-xl border border-emerald-100">
                        {scenarioMet ? (
                          <div className="p-2 bg-emerald-100 text-emerald-700 rounded-lg">
                            <CheckCircle size={20} />
                          </div>
                        ) : (
                          <div className="p-2 bg-rose-100 text-rose-700 rounded-lg">
                            <AlertTriangle size={20} />
                          </div>
                        )}
                        <div>
                          <div className="text-sm font-bold text-slate-800">
                            {scenarioMet
                              ? "Scenario Intervention Successfully Bridged the Target Gap!"
                              : `Scenario Shortfall: Remains ${Math.round(scenarioGap).toLocaleString()} ${activeMetric?.unit} above target.`}
                          </div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            {scenarioMet
                              ? `The simulated ${scenarioForecast.scenario_name} offsets the carbon overshoot.`
                              : "Increase the reduction slider to completely bridge the gap."}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}

        </div>
      </div>
    </motion.div>
  );
};

export default TrendDashboard;
