// Regulatory Intelligence Engine — Core State Management
const State = {
    currentView: 'dashboard', // dashboard, matrix, reviewer, settings, audit, whatif
    projects: [],
    products: [],
    users: [],
    currentUser: null,
    selectedProjectId: null,
    selectedProject: null,
    matrixItems: [],
    selectedMatrixItem: null,
    matrixFilter: 'all',
    matrixSearchQuery: '',
    editorTab: 'narrative', // narrative, json
    whatIfTemplates: [],
    whatIfScenarios: [],
    settings: {
        groq_api_key_configured: false,
        default_model: 'llama3-70b-8192'
    }
};

const API = {
    async fetch(url, options = {}) {
        try {
            const res = await fetch(url, options);
            if (!res.ok) {
                const err = await res.json().catch(() => ({ detail: 'Network request failed' }));
                throw new Error(err.detail || 'Request failed');
            }
            return await res.json();
        } catch (e) {
            console.error(`API Error on ${url}:`, e);
            alert(`Error: ${e.message}`);
            throw e;
        }
    },

    getProjects() { return this.fetch('/api/projects'); },
    getProducts() { return this.fetch('/api/products'); },
    getUsers() { return this.fetch('/api/users'); },
    getAuditLogs(projectId) { return this.fetch(`/api/projects/${projectId}/audit-logs`); },
    createProject(data) {
        return this.fetch('/api/projects', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    deleteProject(id) {
        return this.fetch(`/api/projects/${id}`, { method: 'DELETE' });
    },
    getMatrix(projectId) { return this.fetch(`/api/projects/${projectId}/matrix`); },
    processAI(projectId) { return this.fetch(`/api/projects/${projectId}/process`, { method: 'POST' }); },
    validateProject(projectId) { return this.fetch(`/api/projects/${projectId}/validate`, { method: 'POST' }); },
    getDocuments(projectId) { return this.fetch(`/api/projects/${projectId}/documents`); },
    
    updateAnswer(answerId, data) {
        return this.fetch(`/api/answers/${answerId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    approveAnswer(answerId, reviewerId) {
        let url = `/api/answers/${answerId}/approve`;
        if (reviewerId) url += `?reviewer_id=${reviewerId}`;
        return this.fetch(url, { method: 'POST' });
    },
    rejectAnswer(answerId, reviewerId) {
        let url = `/api/answers/${answerId}/reject`;
        if (reviewerId) url += `?reviewer_id=${reviewerId}`;
        return this.fetch(url, { method: 'POST' });
    },
    
    getSettings() { return this.fetch('/api/settings'); },
    saveSettings(data) {
        return this.fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    
    // New endpoints
    getRegulationFields(framework) {
        let url = '/api/regulation-fields';
        if (framework) url += `?framework=${framework}`;
        return this.fetch(url);
    },
    getCrossReferences(fieldId) { return this.fetch(`/api/regulation-fields/${fieldId}/cross-references`); },
    getWhatIfTemplates() { return this.fetch('/api/what-if/templates'); },
    runWhatIf(projectId, data) {
        return this.fetch(`/api/projects/${projectId}/what-if`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    getWhatIfScenarios(projectId) { return this.fetch(`/api/projects/${projectId}/what-if`); },
    getLegalSummary(projectId) { return this.fetch(`/api/projects/${projectId}/legal-summary`); }
};

// --- DOM Navigation & Renderer ---

function setView(viewName) {
    State.currentView = viewName;
    
    // Toggle active classes on sidebar
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.toggle('active', el.dataset.view === viewName);
    });

    // Hide all containers
    document.querySelectorAll('.view-container').forEach(el => el.style.display = 'none');
    
    // Show active container
    const activeEl = document.getElementById(`${viewName}-view`);
    if (activeEl) {
        activeEl.style.display = 'flex';
        activeEl.classList.add('fade-in');
    }

    if (viewName === 'dashboard') {
        renderDashboard();
    } else if (viewName === 'matrix' && State.selectedProjectId) {
        renderMatrix();
    } else if (viewName === 'settings') {
        renderSettings();
    } else if (viewName === 'audit' && State.selectedProjectId) {
        renderAuditTrail();
    } else if (viewName === 'whatif' && State.selectedProjectId) {
        renderWhatIfView();
    }
}

// User / Role switcher init
async function initUsers() {
    try {
        State.users = await API.getUsers();
        const select = document.getElementById('user-role-select');
        if (select) {
            select.innerHTML = '';
            State.users.forEach(u => {
                select.innerHTML += `<option value="${u.id}">${u.username} (${u.role})</option>`;
            });
            if (State.users.length > 0) {
                State.currentUser = State.users[0];
                updateAvatar(State.currentUser.username);
            }
        }
    } catch (e) {
        console.error("Failed to load users:", e);
    }
}

function switchUserRole() {
    const select = document.getElementById('user-role-select');
    const userId = select.value;
    State.currentUser = State.users.find(u => u.id === userId);
    if (State.currentUser) {
        updateAvatar(State.currentUser.username);
        // Re-render context views
        if (State.currentView === 'matrix') {
            renderMatrix();
        } else if (State.currentView === 'reviewer' && State.selectedMatrixItem) {
            openReviewer(State.selectedMatrixItem.field_id);
        }
    }
}

function updateAvatar(username) {
    const avatar = document.getElementById('active-user-avatar');
    if (avatar && username) {
        avatar.innerText = username.charAt(0).toUpperCase();
    }
}

// --- Penalty Tier Badge Helper ---
function renderPenaltyBadge(tier) {
    const tierConfig = {
        Critical: { class: 'penalty-critical', icon: '🔴', label: 'Critical' },
        High: { class: 'penalty-high', icon: '🟠', label: 'High' },
        Medium: { class: 'penalty-medium', icon: '🟡', label: 'Medium' },
        Low: { class: 'penalty-low', icon: '🟢', label: 'Low' }
    };
    const config = tierConfig[tier] || tierConfig['Medium'];
    return `<span class="penalty-badge ${config.class}" title="Legal Risk: ${config.label}">${config.icon} ${config.label}</span>`;
}

// Render Dashboard View
async function renderDashboard() {
    showLoader(true);
    try {
        State.projects = await API.getProjects();
        State.products = await API.getProducts();
        
        // Populate products dropdown in create modal
        const productSelect = document.getElementById('proj-product');
        if (productSelect) {
            productSelect.innerHTML = '<option value="">Entity-Level PAI Statement</option>';
            State.products.forEach(p => {
                productSelect.innerHTML += `<option value="${p.id}">${p.name} (${p.sfdr_article})</option>`;
            });
        }

        // Render projects grid
        const grid = document.getElementById('projects-grid');
        if (State.projects.length === 0) {
            grid.innerHTML = `
            <div class="glass-card" style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-secondary);">
                <h3>No active compliance projects found</h3>
                <p style="margin-top: 10px;">Click "Create Project" above to start drafting your first regulatory compliance disclosure.</p>
            </div>`;
            updateDashboardKPIs(0, 0, 0);
            showLoader(false);
            return;
        }

        let totalProgress = 0;
        let completedProjects = 0;
        let totalDocs = 0;

        grid.innerHTML = '';
        State.projects.forEach(p => {
            totalProgress += p.progress;
            if (p.status === 'Completed') completedProjects++;
            totalDocs += p.document_count;

            grid.innerHTML += `
            <div class="glass-card project-card fade-in" onclick="selectProject('${p.id}')">
                <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 12px;">
                    <h3 style="color:#fff; font-size:1.15rem;">${p.name}</h3>
                    <span class="badge ${p.status === 'Completed' ? 'badge-approved' : p.status === 'Validating' ? 'badge-draft' : 'badge-missing'}">${p.status}</span>
                </div>
                <p style="color:var(--text-secondary); font-size:0.85rem; margin-bottom: 16px;">
                    ${p.product_name} • ${p.disclosure_type === 'entity_pai' ? 'Entity PAI' : 'Periodic Annex'}
                </p>
                <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:var(--text-muted);">
                    <span>Completion: ${p.progress}%</span>
                    <span>${p.document_count} doc(s)</span>
                </div>
                <div class="progress-bar-container">
                    <div class="progress-bar" style="width: ${p.progress}%"></div>
                </div>
                <div class="project-meta">
                    <span>Period: ${p.reporting_period_start} to ${p.reporting_period_end}</span>
                    <button class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem;" onclick="deleteProject(event, '${p.id}')">Delete</button>
                </div>
            </div>`;
        });

        const avgProgress = State.projects.length ? Math.round(totalProgress / State.projects.length) : 0;
        updateDashboardKPIs(State.projects.length, completedProjects, totalDocs, avgProgress);

    } finally {
        showLoader(false);
    }
}

function updateDashboardKPIs(total, completed, docs, avgProgress = 0) {
    document.getElementById('kpi-total-projects').innerText = total;
    document.getElementById('kpi-completed-projects').innerText = completed;
    document.getElementById('kpi-total-documents').innerText = docs;
    document.getElementById('kpi-avg-progress').innerText = `${avgProgress}%`;
}

async function selectProject(projectId) {
    State.selectedProjectId = projectId;
    State.selectedProject = State.projects.find(p => p.id === projectId);
    
    // Enable matrix, audit, and what-if navigation tabs
    document.getElementById('nav-matrix').style.display = 'flex';
    document.getElementById('nav-audit').style.display = 'flex';
    document.getElementById('nav-whatif').style.display = 'flex';
    setView('matrix');
}

// Render Requirement Matrix (Main Table view)
async function renderMatrix() {
    if (!State.selectedProjectId) return;
    
    showLoader(true);
    document.getElementById('matrix-project-title').innerText = State.selectedProject.name;
    
    try {
        State.matrixItems = await API.getMatrix(State.selectedProjectId);
        const docs = await API.getDocuments(State.selectedProjectId);

        // Render document chips list
        const docsList = document.getElementById('uploaded-docs-list');
        docsList.innerHTML = '';
        if (docs.length === 0) {
            docsList.innerHTML = '<span style="color:var(--text-muted); font-size:0.85rem;">No documents uploaded yet.</span>';
        } else {
            docs.forEach(d => {
                docsList.innerHTML += `
                <div class="badge badge-approved" style="display:inline-flex; align-items:center; gap:6px; margin-right:8px; margin-bottom:8px;">
                    <svg style="width:12px; height:12px; fill:none; stroke:currentColor; stroke-width:2;" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                    ${d.file_name}
                </div>`;
            });
        }

        // Calculate and render overall matrix progress
        const totalFields = State.matrixItems.length;
        const approvedFields = State.matrixItems.filter(m => m.answer_status === 'Approved').length;
        const matrixProgress = totalFields > 0 ? Math.round((approvedFields / totalFields) * 100) : 0;
        
        document.getElementById('matrix-progress-text').innerText = `Approved ${approvedFields} of ${totalFields} disclosure requirements`;
        document.getElementById('matrix-progress-percentage').innerText = `${matrixProgress}%`;
        document.getElementById('matrix-progress-bar').style.width = `${matrixProgress}%`;

        // Render matrix rows using active filters
        renderMatrixTable();

        // Render Automated Validation Console
        renderComplianceConsole();

    } finally {
        showLoader(false);
    }
}

function renderMatrixTable() {
    const tbody = document.getElementById('matrix-table-body');
    tbody.innerHTML = '';

    State.matrixItems.forEach(item => {
        // Apply status filter
        if (State.matrixFilter !== 'all' && item.answer_status !== State.matrixFilter) return;

        // Apply search query
        if (State.matrixSearchQuery) {
            const query = State.matrixSearchQuery;
            const matchLabel = item.field_label.toLowerCase().includes(query);
            const matchCode = item.field_code.toLowerCase().includes(query);
            const matchAnnex = (item.annex_code || '').toLowerCase().includes(query);
            if (!matchLabel && !matchCode && !matchAnnex) return;
        }

        let statusBadge = 'badge-missing';
        if (item.answer_status === 'Approved') statusBadge = 'badge-approved';
        else if (item.answer_status === 'Draft') statusBadge = 'badge-draft';
        else if (item.answer_status === 'Rejected') statusBadge = 'badge-rejected';

        // Extract value visualization
        let displayVal = 'N/A';
        if (item.extracted_value) {
            if (typeof item.extracted_value === 'object' && item.extracted_value.value !== undefined) {
                displayVal = `${item.extracted_value.value} ${item.extracted_value.unit || ''}`;
            } else if (Array.isArray(item.extracted_value)) {
                displayVal = `${item.extracted_value.length} items`;
            } else {
                displayVal = item.extracted_value;
            }
        }

        // Validation indicators
        let valIndicators = '<span style="color:var(--accent-emerald); font-weight:bold;">Passed</span>';
        if (!item.validation_passed) {
            valIndicators = item.validation_errors.map(err => `<div class="warning-pill">${err}</div>`).join('');
        }

        // High contrast mandatory indicator
        const mandatoryTag = item.mandatory 
            ? `<span style="color:var(--accent-coral); font-weight:bold; font-size:1.1rem; vertical-align:middle; margin-left:4px;" title="Mandatory Field">*</span>` 
            : '';

        // Legal risk column (NEW)
        const penaltyBadge = renderPenaltyBadge(item.penalty_tier || 'Medium');

        tbody.innerHTML += `
        <tr onclick="openReviewer('${item.field_id}')" style="cursor:pointer;">
            <td style="font-weight:600; color:#fff;">${item.field_label}${mandatoryTag}</td>
            <td><code>${item.field_code}</code></td>
            <td>${penaltyBadge}</td>
            <td><span class="badge ${statusBadge}">${item.answer_status}</span></td>
            <td><strong style="color:var(--accent-cyan);">${displayVal}</strong></td>
            <td style="max-width:200px;">${valIndicators}</td>
        </tr>`;
    });
}

function filterMatrix() {
    const searchInput = document.getElementById('matrix-search');
    State.matrixSearchQuery = searchInput ? searchInput.value.toLowerCase().trim() : '';
    renderMatrixTable();
}

function setMatrixFilter(btn) {
    document.querySelectorAll('.filter-btn').forEach(el => el.classList.remove('active'));
    btn.classList.add('active');
    State.matrixFilter = btn.dataset.filter;
    renderMatrixTable();
}

function renderComplianceConsole() {
    const issuesContainer = document.getElementById('compliance-console-issues');
    const flagCountBadge = document.getElementById('console-flag-count');
    const escalationBadge = document.getElementById('console-escalation-count');
    if (!issuesContainer) return;

    issuesContainer.innerHTML = '';
    let totalFlags = 0;
    let escalationCount = 0;

    // Gather failing matrix items with enriched legal consequence data
    const failingItems = State.matrixItems.filter(item => !item.validation_passed);
    
    if (failingItems.length === 0) {
        issuesContainer.innerHTML = `
        <div style="padding: 20px; text-align: center; color: var(--accent-emerald); font-weight: 500; font-size: 0.9rem;">
            ✔ 100% Compliant. No active warnings or validation errors flagged by the rules engine.
        </div>`;
        flagCountBadge.innerText = '0 Flags';
        flagCountBadge.className = 'badge badge-approved';
        if (escalationBadge) {
            escalationBadge.innerText = '0 Escalations';
            escalationBadge.className = 'badge badge-approved';
        }
        return;
    }

    failingItems.forEach(item => {
        // Use enriched legal_consequences if available, otherwise fall back to errors
        const consequences = item.legal_consequences || [];
        
        if (consequences.length > 0) {
            consequences.forEach(lc => {
                totalFlags++;
                if (lc.escalation_required) escalationCount++;

                const severityBadge = lc.severity === 'Error' ? 'badge-missing' 
                    : lc.severity === 'Info' ? 'badge-approved' : 'badge-draft';
                
                const escalationTag = lc.escalation_required 
                    ? '<span class="badge penalty-critical" style="margin-left:6px;">⚡ ESCALATION</span>' : '';

                issuesContainer.innerHTML += `
                <div class="legal-consequence-card ${lc.escalation_required ? 'escalation' : ''}">
                    <div class="lc-header">
                        <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                            <span class="badge ${severityBadge}">${lc.severity}</span>
                            ${renderPenaltyBadge(item.penalty_tier || 'Medium')}
                            ${escalationTag}
                            <strong style="color:#fff; font-size:0.9rem;">${item.field_label}</strong>
                        </div>
                        <button class="btn btn-secondary" style="padding:6px 12px; font-size:0.75rem; flex-shrink:0;" onclick="openReviewer('${item.field_id}')">
                            Audit Field
                        </button>
                    </div>
                    <div class="lc-body">
                        <p style="color:var(--text-secondary); font-size:0.85rem;">${lc.message}</p>
                        ${lc.regulation_ref ? `<div class="lc-reg-ref">📜 <strong>Legal Basis:</strong> ${lc.regulation_ref}</div>` : ''}
                        ${lc.legal_consequence ? `<div class="lc-consequence">⚖️ <strong>Legal Consequence:</strong> ${lc.legal_consequence}</div>` : ''}
                        ${lc.penalty_range ? `<div class="lc-penalty">💰 <strong>Penalty Range:</strong> ${lc.penalty_range}</div>` : ''}
                        ${lc.remediation ? `
                        <details class="lc-remediation">
                            <summary>🔧 Remediation Playbook</summary>
                            <pre>${lc.remediation}</pre>
                        </details>` : ''}
                    </div>
                </div>`;
            });
        } else {
            // Fallback to basic error display
            item.validation_errors.forEach(err => {
                totalFlags++;
                issuesContainer.innerHTML += `
                <div class="compliance-issue-card warning">
                    <div style="display:flex; flex-direction:column; gap:4px;">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <span class="badge badge-draft">Warning</span>
                            <strong style="color:#fff; font-size:0.9rem;">${item.field_label} (<code>${item.field_code}</code>)</strong>
                        </div>
                        <p style="color:var(--text-secondary); font-size:0.85rem; margin-top:2px;">${err}</p>
                    </div>
                    <button class="btn btn-secondary" style="padding:6px 12px; font-size:0.75rem;" onclick="openReviewer('${item.field_id}')">
                        Audit Field
                    </button>
                </div>`;
            });
        }
    });

    flagCountBadge.innerText = `${totalFlags} Flags`;
    flagCountBadge.className = 'badge badge-rejected';
    if (escalationBadge) {
        escalationBadge.innerText = `${escalationCount} Escalations`;
        escalationBadge.className = escalationCount > 0 ? 'badge badge-rejected' : 'badge badge-approved';
    }
}

// Open Side-by-Side Reviewer Workspace
function openReviewer(fieldId) {
    const item = State.matrixItems.find(m => m.field_id === fieldId);
    if (!item) return;

    State.selectedMatrixItem = item;
    
    // Set UI active tab
    document.getElementById('nav-reviewer').style.display = 'flex';
    setView('reviewer');

    // Populate Right Pane (AI Editor)
    document.getElementById('rev-field-title').innerText = item.field_label;
    document.getElementById('rev-field-code').innerText = item.field_code;
    document.getElementById('rev-field-desc').innerText = item.description || 'No direct RTS framework guidelines pre-seeded.';
    document.getElementById('rev-expected-unit').innerText = item.expected_unit ? `Standard Expected Unit: ${item.expected_unit}` : 'Expected Unit: Narrative / N/A';

    const editor = document.getElementById('rev-editor-text');
    editor.value = item.answer_text || '';

    // Set badges and validation rules in reviewer
    const statusEl = document.getElementById('rev-field-status');
    statusEl.className = `badge badge-${item.answer_status.toLowerCase()}`;
    statusEl.innerText = item.answer_status;

    // Display validation errors list
    const errList = document.getElementById('rev-validation-errors');
    errList.innerHTML = '';
    if (item.validation_passed) {
        errList.innerHTML = '<div class="badge badge-approved" style="width:100%; display:block;">✔ Automated Validation: 100% Compliant</div>';
    } else {
        item.validation_errors.forEach(err => {
            errList.innerHTML += `<div class="error-pill">⚠ ${err}</div>`;
        });
    }

    // Populate Left Pane (Document Evidence Viewer)
    const quoteBox = document.getElementById('rev-evidence-quote');
    const sourceMeta = document.getElementById('rev-source-meta');
    
    if (item.evidence_quote) {
        quoteBox.innerHTML = `
        <div class="highlight-box">
            "${item.evidence_quote}"
        </div>`;
        sourceMeta.innerHTML = `
        <div style="font-size:0.85rem; color:var(--text-secondary); line-height: 1.6;">
            <strong>Source Document:</strong> ${item.source_file || 'Primary Report'}<br>
            <strong>Location:</strong> Page ${item.page_no || 1}<br>
            <strong>Extraction Accuracy Confidence:</strong> <span style="color:var(--accent-cyan); font-weight:700;">${Math.round(item.confidence * 100)}%</span>
        </div>`;
    } else {
        quoteBox.innerHTML = '<p style="color:var(--text-muted); font-style:italic;">No supporting audit citation could be located by the hybrid retrieval engine.</p>';
        sourceMeta.innerHTML = '<p style="color:var(--text-muted); font-size:0.85rem;">Run AI Extraction to scan documents.</p>';
    }

    // Render Legal Risk Section (NEW)
    renderLegalRiskSection(item);
    
    // Render Cross-Framework Links (NEW)
    renderCrossRefSection(item);

    // Default to Narrative Editor tab
    switchEditorTab('narrative');
    
    // Render the structured JSON tab content
    renderStructuredJSONEditor();
}

function renderLegalRiskSection(item) {
    const section = document.getElementById('rev-legal-risk-section');
    if (!section) return;

    section.innerHTML = `
    <div style="display:flex; align-items:center; gap:8px; border-bottom:1px solid var(--border-light); padding-bottom:12px; margin-bottom:12px;">
        <h3 style="color:#fff; font-size:1rem;">⚖️ Legal Risk Profile</h3>
        ${renderPenaltyBadge(item.penalty_tier || 'Medium')}
    </div>
    <div style="display:flex; flex-direction:column; gap:10px;">
        <div class="legal-detail-row">
            <span class="legal-detail-label">Legal Basis</span>
            <span class="legal-detail-value">${item.legal_basis || 'Not specified'}</span>
        </div>
        <div class="legal-detail-row">
            <span class="legal-detail-label">Enforcement Body</span>
            <span class="legal-detail-value">${item.enforcement_body || 'National Competent Authority'}</span>
        </div>
        <div class="legal-detail-row">
            <span class="legal-detail-label">Penalty Tier</span>
            <span class="legal-detail-value">${renderPenaltyBadge(item.penalty_tier || 'Medium')}</span>
        </div>
        <div class="legal-detail-row">
            <span class="legal-detail-label">Mandatory</span>
            <span class="legal-detail-value">${item.mandatory ? '<span style="color:var(--accent-coral); font-weight:700;">Yes — Required</span>' : '<span style="color:var(--accent-emerald);">Optional</span>'}</span>
        </div>
    </div>
    ${(item.legal_consequences && item.legal_consequences.length > 0) ? `
    <div style="margin-top:16px; border-top:1px solid var(--border-light); padding-top:12px;">
        <h4 style="color:var(--accent-coral); font-size:0.85rem; margin-bottom:8px;">Active Legal Consequences</h4>
        ${item.legal_consequences.map(lc => `
        <div class="lc-mini-card">
            <p style="font-size:0.8rem; color:var(--text-secondary);">${lc.legal_consequence || lc.message}</p>
            ${lc.penalty_range ? `<span style="font-size:0.75rem; color:var(--accent-gold);">💰 ${lc.penalty_range}</span>` : ''}
        </div>`).join('')}
    </div>` : ''}`;
}

function renderCrossRefSection(item) {
    const section = document.getElementById('rev-cross-ref-section');
    if (!section) return;

    const refs = item.cross_references || [];
    
    if (refs.length === 0) {
        section.innerHTML = `
        <h3 style="color:#fff; font-size:1rem; border-bottom:1px solid var(--border-light); padding-bottom:12px;">🔗 Cross-Framework Links</h3>
        <p style="color:var(--text-muted); font-size:0.85rem; margin-top:12px;">No cross-framework references mapped for this field.</p>`;
        return;
    }

    section.innerHTML = `
    <h3 style="color:#fff; font-size:1rem; border-bottom:1px solid var(--border-light); padding-bottom:12px;">🔗 Cross-Framework Links</h3>
    <div style="display:flex; flex-direction:column; gap:8px; margin-top:12px;">
        ${refs.map(ref => `
        <div class="cross-ref-card">
            <div style="display:flex; align-items:center; gap:8px;">
                <span class="cross-ref-framework-badge">${ref.framework}</span>
                <code style="font-size:0.8rem; color:var(--accent-cyan);">${ref.field_code}</code>
            </div>
            <span class="cross-ref-relationship">${formatRelationship(ref.relationship)}</span>
        </div>`).join('')}
    </div>`;
}

function formatRelationship(rel) {
    const labels = {
        'equivalent_disclosure': '≡ Equivalent',
        'complementary_indicator': '↔ Complementary',
        'supplementary_data': '+ Supplementary',
        'data_dependency': '⬇ Data Dependency',
        'derived_metric': '∑ Derived Metric',
        'exclusion_alignment': '⊘ Exclusion Alignment',
        'direct_dependency': '⬇ Direct Dependency'
    };
    return labels[rel] || rel;
}

function switchEditorTab(tabName) {
    State.editorTab = tabName;
    document.querySelectorAll('.editor-tab').forEach(el => {
        el.classList.toggle('active', el.id === `tab-${tabName}-btn`);
    });
    document.querySelectorAll('.editor-pane').forEach(el => {
        el.classList.toggle('active', el.id === `pane-${tabName}`);
    });
}

function renderStructuredJSONEditor() {
    const container = document.getElementById('json-editor-container');
    if (!container || !State.selectedMatrixItem) return;

    container.innerHTML = '';
    const item = State.selectedMatrixItem;

    if (item.field_kind === 'numeric') {
        // Numeric field - Value and Unit inputs
        let val = '';
        let unit = item.expected_unit || '';
        
        if (item.extracted_value && typeof item.extracted_value === 'object') {
            val = item.extracted_value.value ?? '';
            unit = item.extracted_value.unit ?? unit;
        } else if (item.extracted_value !== undefined) {
            val = item.extracted_value;
        }

        container.innerHTML = `
        <div class="json-field-row">
            <div class="form-group" style="flex: 2;">
                <label for="json-val-input">Extracted Numeric Value</label>
                <input type="number" step="any" id="json-val-input" class="form-input" value="${val}">
            </div>
            <div class="form-group" style="flex: 1;">
                <label for="json-unit-input">Reporting Unit</label>
                <input type="text" id="json-unit-input" class="form-input" value="${unit}">
            </div>
        </div>
        <p style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">Expected unit for this field: <strong>${item.expected_unit || 'N/A'}</strong>.</p>
        `;
    } else if (item.field_kind === 'table') {
        // Table fields (like periodic holdings) - Interactive rows grid
        let holdings = [];
        if (item.extracted_value && Array.isArray(item.extracted_value)) {
            holdings = item.extracted_value;
        } else if (item.answer_json && Array.isArray(item.answer_json.holdings)) {
            holdings = item.answer_json.holdings;
        }

        container.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
            <span style="font-size:0.8rem; font-weight:600; color:var(--text-secondary);">Holdings Grid (max 15)</span>
            <button class="btn btn-secondary" style="padding:4px 8px; font-size:0.75rem;" onclick="addHoldingRow()">+ Add Row</button>
        </div>
        <div style="overflow-x:auto;">
            <table class="json-grid-table">
                <thead>
                    <tr>
                        <th>Asset Name</th>
                        <th>Weight</th>
                        <th>Sector</th>
                        <th>Country</th>
                        <th></th>
                    </tr>
                </thead>
                <tbody id="json-holdings-tbody">
                    <!-- Rendered dynamically -->
                </tbody>
            </table>
        </div>
        `;
        const tbody = document.getElementById('json-holdings-tbody');
        if (holdings.length === 0) {
            holdings.push({name: '', weight: '', sector: '', country: ''});
        }
        holdings.forEach(h => appendHoldingRowMarkup(tbody, h));
    } else {
        // Narrative / Fallback - Raw JSON editor
        const rawData = item.answer_json || item.extracted_value || {};
        container.innerHTML = `
        <textarea id="json-raw-textarea" class="editor-box" style="font-family: monospace; font-size: 0.85rem; min-height: 250px;">${JSON.stringify(rawData, null, 2)}</textarea>
        <p style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">Conforms to general metadata schemas.</p>
        `;
    }
}

function appendHoldingRowMarkup(tbody, h) {
    const tr = document.createElement('tr');
    tr.className = 'json-holding-row';
    tr.innerHTML = `
    <td><input type="text" class="json-grid-input holding-name" value="${h.name || ''}" placeholder="e.g. Vestas"></td>
    <td><input type="text" class="json-grid-input holding-weight" value="${h.weight || ''}" placeholder="e.g. 4.2%"></td>
    <td><input type="text" class="json-grid-input holding-sector" value="${h.sector || ''}" placeholder="e.g. Wind Energy"></td>
    <td><input type="text" class="json-grid-input holding-country" value="${h.country || ''}" placeholder="e.g. Denmark"></td>
    <td>
        <button class="btn btn-secondary" style="padding:4px; min-width:24px; color:var(--accent-coral); border:none;" onclick="this.closest('tr').remove()">✕</button>
    </td>
    `;
    tbody.appendChild(tr);
}

function addHoldingRow() {
    const tbody = document.getElementById('json-holdings-tbody');
    if (tbody) {
        appendHoldingRowMarkup(tbody, {name:'', weight:'', sector:'', country:''});
    }
}

// ===========================
// WHAT-IF SIMULATOR (NEW)
// ===========================

async function renderWhatIfView() {
    showLoader(true);
    try {
        // Load templates and past scenarios
        State.whatIfTemplates = await API.getWhatIfTemplates();
        State.whatIfScenarios = await API.getWhatIfScenarios(State.selectedProjectId);

        // Render template cards
        const grid = document.getElementById('whatif-template-grid');
        grid.innerHTML = '';

        State.whatIfTemplates.forEach((tpl, idx) => {
            const actionIcon = tpl.parameters.action === 'remove_field' ? '🚫' 
                : tpl.parameters.action === 'threshold_change' ? '📉' : '🔄';
            
            grid.innerHTML += `
            <div class="whatif-template-card glass-card fade-in" onclick="runWhatIfScenario(${idx})">
                <div class="whatif-template-icon">${actionIcon}</div>
                <h4 style="color:#fff; font-size:0.95rem;">${tpl.scenario_name}</h4>
                <p style="color:var(--text-secondary); font-size:0.8rem; margin-top:6px;">${tpl.scenario_description}</p>
                <div style="margin-top:12px;">
                    <span class="btn btn-secondary" style="padding:6px 14px; font-size:0.8rem;">Run Simulation →</span>
                </div>
            </div>`;
        });

        // Render history
        renderWhatIfHistory();

    } finally {
        showLoader(false);
    }
}

async function runWhatIfScenario(templateIndex) {
    const tpl = State.whatIfTemplates[templateIndex];
    if (!tpl) return;

    showLoader(true);
    try {
        const result = await API.runWhatIf(State.selectedProjectId, {
            scenario_name: tpl.scenario_name,
            scenario_description: tpl.scenario_description,
            parameters: tpl.parameters
        });

        // Show results panel
        const panel = document.getElementById('whatif-results-panel');
        panel.style.display = 'flex';

        document.getElementById('whatif-result-title').innerText = result.scenario_name;

        // Risk gauge
        const gauge = document.getElementById('whatif-risk-gauge');
        const scoreEl = document.getElementById('whatif-risk-score');
        scoreEl.innerText = Math.round(result.risk_score);
        
        gauge.className = 'risk-gauge';
        if (result.risk_score >= 75) gauge.classList.add('risk-critical');
        else if (result.risk_score >= 50) gauge.classList.add('risk-high');
        else if (result.risk_score >= 25) gauge.classList.add('risk-medium');
        else gauge.classList.add('risk-low');

        // Triggered obligations
        const oblContainer = document.getElementById('whatif-obligations');
        oblContainer.innerHTML = '';
        const obligations = result.triggered_obligations || [];
        obligations.forEach(obl => {
            oblContainer.innerHTML += `
            <div class="whatif-obligation-card">
                <div style="display:flex; align-items:center; gap:8px;">
                    <span class="cross-ref-framework-badge">${obl.regulation_article || 'Regulation'}</span>
                </div>
                <p style="color:var(--text-secondary); font-size:0.85rem; margin-top:6px;">${obl.description}</p>
            </div>`;
        });

        // Legal consequences
        const consContainer = document.getElementById('whatif-consequences');
        consContainer.innerHTML = '';
        const consequences = result.legal_consequences || [];
        consequences.forEach(con => {
            const sevClass = con.severity === 'High' ? 'penalty-high' 
                : con.severity === 'Medium' ? 'penalty-medium'
                : con.severity === 'Info' ? 'penalty-low' : 'penalty-critical';
            
            consContainer.innerHTML += `
            <div class="whatif-consequence-card">
                <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
                    <span class="penalty-badge ${sevClass}">${con.severity}</span>
                    <span style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase;">${con.type}</span>
                </div>
                <p style="color:var(--text-secondary); font-size:0.85rem;">${con.description}</p>
            </div>`;
        });

        // Refresh history
        State.whatIfScenarios = await API.getWhatIfScenarios(State.selectedProjectId);
        renderWhatIfHistory();

        // Scroll to results
        panel.scrollIntoView({ behavior: 'smooth' });

    } finally {
        showLoader(false);
    }
}

function renderWhatIfHistory() {
    const container = document.getElementById('whatif-history');
    if (!container) return;

    container.innerHTML = '';

    if (State.whatIfScenarios.length === 0) {
        container.innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:20px;">No simulations run yet. Select a scenario above to get started.</p>';
        return;
    }

    State.whatIfScenarios.forEach(sc => {
        const dateStr = new Date(sc.created_at).toLocaleString();
        const riskClass = sc.risk_score >= 75 ? 'risk-critical' : sc.risk_score >= 50 ? 'risk-high' : sc.risk_score >= 25 ? 'risk-medium' : 'risk-low';
        
        container.innerHTML += `
        <div class="whatif-history-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <strong style="color:#fff;">${sc.scenario_name}</strong>
                    <span style="color:var(--text-muted); font-size:0.8rem; margin-left:8px;">${dateStr}</span>
                </div>
                <div class="risk-gauge-mini ${riskClass}">
                    <span>${Math.round(sc.risk_score)}</span>
                </div>
            </div>
            <p style="color:var(--text-secondary); font-size:0.8rem; margin-top:4px;">${sc.scenario_description || ''}</p>
        </div>`;
    });
}


// Render Audit Trail View
async function renderAuditTrail() {
    if (!State.selectedProjectId) return;
    
    showLoader(true);
    document.getElementById('audit-project-title').innerText = `${State.selectedProject.name} - Audit Trail`;
    
    try {
        const logs = await API.getAuditLogs(State.selectedProjectId);
        const container = document.getElementById('audit-timeline-container');
        container.innerHTML = '';
        
        if (logs.length === 0) {
            container.innerHTML = '<div style="color:var(--text-secondary); text-align:center; padding:40px;">No compliance activities recorded for this project yet.</div>';
            return;
        }

        logs.forEach(log => {
            const dateStr = new Date(log.created_at).toLocaleString();
            let icon = '✦';
            let actionClass = 'create';
            
            if (log.action === 'upload') { icon = '📥'; actionClass = 'upload'; }
            else if (log.action === 'approve') { icon = '✓'; actionClass = 'approve'; }
            else if (log.action === 'reject') { icon = '✕'; actionClass = 'reject'; }
            else if (log.action === 'manual_edit') { icon = '✏️'; actionClass = 'modify'; }
            else if (log.action === 'process_ai') { icon = '🤖'; actionClass = 'modify'; }
            else if (log.action === 'validate') { icon = '🛡️'; actionClass = 'modify'; }
            else if (log.action === 'simulate') { icon = '🧪'; actionClass = 'modify'; }
            
            const actorDisplay = log.actor_username ? `${log.actor_username} (${log.actor_role})` : 'System Processes';
            let actionText = `${log.action.replace('_', ' ').toUpperCase()}`;
            if (log.action === 'manual_edit') actionText = 'Manual Revision Saved';
            if (log.action === 'simulate') actionText = 'What-If Simulation';

            let payloadStr = '';
            if (log.payload && Object.keys(log.payload).length > 0) {
                payloadStr = `
                <details style="margin-top:8px; cursor:pointer;">
                    <summary style="font-size:0.75rem; color:var(--accent-indigo); font-weight:600;">View Activity Payload</summary>
                    <pre class="timeline-payload">${JSON.stringify(log.payload, null, 2)}</pre>
                </details>`;
            }

            container.innerHTML += `
            <div class="timeline-item ${actionClass} fade-in">
                <div class="timeline-marker">${icon}</div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-actor">${actorDisplay}</span>
                        <span>${dateStr}</span>
                    </div>
                    <div class="timeline-action-text">
                        <strong>${actionText}</strong>: Mapped to ${log.entity_type} (ID: <code>${log.entity_id.substring(0, 8)}...</code>)
                      </div>
                      ${payloadStr}
                  </div>
              </div>`;
        });
    } finally {
        showLoader(false);
    }
}

// --- Action Handlers ---

// Save edited draft
async function saveReviewerDraft() {
    if (!State.selectedMatrixItem) return;
    
    const text = document.getElementById('rev-editor-text').value;
    
    // Parse the structured JSON editor state
    let answer_json = null;
    const kind = State.selectedMatrixItem.field_kind;
    
    if (kind === 'numeric') {
        const valEl = document.getElementById('json-val-input');
        const unitEl = document.getElementById('json-unit-input');
        if (valEl) {
            const numVal = valEl.value.trim() !== '' ? parseFloat(valEl.value) : null;
            answer_json = { value: numVal, unit: unitEl ? unitEl.value : '' };
        }
    } else if (kind === 'table') {
        const rows = document.querySelectorAll('.json-holding-row');
        const holdings = [];
        rows.forEach(row => {
            const name = row.querySelector('.holding-name').value.trim();
            const weight = row.querySelector('.holding-weight').value.trim();
            const sector = row.querySelector('.holding-sector').value.trim();
            const country = row.querySelector('.holding-country').value.trim();
            if (name || weight) {
                holdings.push({ name, weight, sector, country });
            }
        });
        answer_json = { holdings, count: holdings.length };
    } else {
        const rawEl = document.getElementById('json-raw-textarea');
        if (rawEl) {
            try {
                answer_json = JSON.parse(rawEl.value);
            } catch (e) {
                alert("Invalid JSON format. Please correct it before saving.");
                return;
            }
        }
    }

    showLoader(true);
    try {
        await API.updateAnswer(State.selectedMatrixItem.answer_id, {
            answer_text: text,
            answer_json: answer_json,
            status: 'Draft',
            approved_by_user_id: State.currentUser ? State.currentUser.id : null
        });
        
        // Refresh local matrix and re-populate current field
        await renderMatrix();
        openReviewer(State.selectedMatrixItem.field_id);
    } finally {
        showLoader(false);
    }
}

// Approve answer
async function approveReviewerDraft() {
    if (!State.selectedMatrixItem) return;
    
    showLoader(true);
    try {
        await API.approveAnswer(
            State.selectedMatrixItem.answer_id, 
            State.currentUser ? State.currentUser.id : null
        );
        await renderMatrix();
        openReviewer(State.selectedMatrixItem.field_id);
    } finally {
        showLoader(false);
    }
}

// Reject answer
async function rejectReviewerDraft() {
    if (!State.selectedMatrixItem) return;
    
    showLoader(true);
    try {
        await API.rejectAnswer(
            State.selectedMatrixItem.answer_id, 
            State.currentUser ? State.currentUser.id : null
        );
        await renderMatrix();
        openReviewer(State.selectedMatrixItem.field_id);
    } finally {
        showLoader(false);
    }
}

// Create new reporting project
async function submitCreateProject() {
    const name = document.getElementById('proj-name').value;
    const disclosure_type = document.getElementById('proj-type').value;
    const start = document.getElementById('proj-start').value;
    const end = document.getElementById('proj-end').value;
    const product_id = document.getElementById('proj-product').value;

    if (!name || !start || !end) {
        alert("Please fill in all mandatory fields.");
        return;
    }

    showLoader(true);
    try {
        const proj = await API.createProject({
            name,
            disclosure_type,
            reporting_period_start: start,
            reporting_period_end: end,
            product_id: product_id || null,
            organization_id: "default_org"
        });
        
        closeModal();
        renderDashboard();
    } finally {
        showLoader(false);
    }
}

// Delete Reporting Project
async function deleteProject(event, projectId) {
    event.stopPropagation(); // Avoid selecting project
    if (!confirm("Are you sure you want to delete this project and all uploaded documents?")) return;
    
    showLoader(true);
    try {
        await API.deleteProject(projectId);
        if (State.selectedProjectId === projectId) {
            State.selectedProjectId = null;
            State.selectedProject = null;
            document.getElementById('nav-matrix').style.display = 'none';
            document.getElementById('nav-reviewer').style.display = 'none';
            document.getElementById('nav-audit').style.display = 'none';
            document.getElementById('nav-whatif').style.display = 'none';
        }
        renderDashboard();
    } finally {
        showLoader(false);
    }
}

// Document Upload Flow (Handles multiple files drop & select)
async function triggerDocUpload(filesToUpload = null) {
    const fileInput = document.getElementById('doc-file-input');
    const sourceSelect = document.getElementById('doc-source-type');
    
    const files = filesToUpload || fileInput.files;
    if (!files || files.length === 0) {
        alert("Please choose one or more files to upload.");
        return;
    }

    const source_type = sourceSelect.value;
    
    // Show upload progress section
    const progressContainer = document.getElementById('upload-progress-container');
    progressContainer.style.display = 'flex';
    progressContainer.innerHTML = '';

    // Create progress row for each file
    const fileList = Array.from(files);
    fileList.forEach((file, index) => {
        progressContainer.innerHTML += `
        <div class="upload-progress-row" id="upload-row-${index}">
            <span style="font-weight:500;">${file.name}</span>
            <span class="badge badge-draft" id="upload-status-${index}">Uploading...</span>
        </div>`;
    });

    showLoader(true);
    
    try {
        const formData = new FormData();
        for (const file of fileList) {
            formData.append('files', file);
        }
        formData.append('source_type', source_type);

        const res = await fetch(`/api/projects/${State.selectedProjectId}/documents/batch`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error("Batch upload request failed.");
        const uploadResults = await res.json();
        
        // Update statuses based on batch response
        fileList.forEach((file, index) => {
            const match = uploadResults.find(r => r.file_name === file.name);
            const statusBadge = document.getElementById(`upload-status-${index}`);
            if (statusBadge) {
                if (match && match.status === 'Completed') {
                    statusBadge.innerText = 'Completed ✔';
                    statusBadge.className = 'badge badge-approved';
                } else {
                    statusBadge.innerText = 'Failed ✖';
                    statusBadge.className = 'badge badge-rejected';
                }
            }
        });
        
        fileInput.value = ''; // clear input
        await renderMatrix(); // reload matrix & documents list
        
        // Hide progress section after 3 seconds
        setTimeout(() => {
            progressContainer.style.display = 'none';
        }, 3000);
        
    } catch (e) {
        alert(`Failed to upload batch: ${e.message}`);
        fileList.forEach((file, index) => {
            const statusBadge = document.getElementById(`upload-status-${index}`);
            if (statusBadge) {
                statusBadge.innerText = 'Failed ✖';
                statusBadge.className = 'badge badge-rejected';
            }
        });
    } finally {
        showLoader(false);
    }
}

// Run GenAI Core Processing (RAG, Extraction, Drafting, Validation)
async function triggerAIProcessing() {
    if (!State.selectedProjectId) return;
    
    const check = confirm("Running GenAI processing will scan all uploaded documents, fetch source evidence using hybrid retrieval, and draft disclosures using Groq Llama3. Do you want to continue?");
    if (!check) return;

    showLoader(true);
    try {
        const res = await API.processAI(State.selectedProjectId);
        alert(res.message);
        await renderMatrix();
    } finally {
        showLoader(false);
    }
}

// Trigger standard compliance validation engine run
async function triggerValidation() {
    if (!State.selectedProjectId) return;
    showLoader(true);
    try {
        const res = await API.validateProject(State.selectedProjectId);
        alert(`${res.message}. Found ${res.errors_warnings_count} compliance notifications.`);
        await renderMatrix();
    } finally {
        showLoader(false);
    }
}

// Drag & drop zone initializer
function initDragDrop() {
    const zone = document.getElementById('drag-drop-zone');
    if (!zone) return;

    zone.addEventListener('dragover', (e) => {
        e.preventDefault();
        zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', () => {
        zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', (e) => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            triggerDocUpload(e.dataTransfer.files);
        }
    });
}

// --- Exports ---
function triggerExportMD() {
    if (!State.selectedProjectId) return;
    window.open(`/api/projects/${State.selectedProjectId}/export/markdown`, '_blank');
}

function triggerExportHTML() {
    if (!State.selectedProjectId) return;
    window.open(`/api/projects/${State.selectedProjectId}/export/html`, '_blank');
}

// --- Settings ---
async function renderSettings() {
    showLoader(true);
    try {
        State.settings = await API.getSettings();
        document.getElementById('set-groq-key').value = '';
        document.getElementById('set-groq-status').innerText = State.settings.groq_api_key_configured 
            ? "API Key Configured (active)" 
            : "No API Key configured. System currently running in Offline High-fidelity Simulation Mode.";
        document.getElementById('set-groq-status').style.color = State.settings.groq_api_key_configured 
            ? 'var(--accent-emerald)' 
            : 'var(--accent-gold)';
    } finally {
        showLoader(false);
    }
}

async function saveSettingsKey() {
    const key = document.getElementById('set-groq-key').value.trim();
    if (!key) {
        alert("Please enter a valid key.");
        return;
    }

    showLoader(true);
    try {
        await API.saveSettings({ groq_api_key: key });
        alert("Groq API key saved successfully.");
        renderSettings();
    } finally {
        showLoader(false);
    }
}

// --- Helper Functions ---

function showLoader(show) {
    const loader = document.getElementById('global-loader');
    if (loader) loader.style.display = show ? 'block' : 'none';
}

function showCreateModal() {
    document.getElementById('create-modal').style.display = 'flex';
}

function closeModal() {
    document.getElementById('create-modal').style.display = 'none';
}

// Initialize application on window load
window.addEventListener('load', async () => {
    // 1. Initial view
    setView('dashboard');
    
    // 2. Load seeded users
    await initUsers();

    // 3. Init drag-and-drop
    initDragDrop();
    
    // 4. Close modal on click overlay
    const modal = document.getElementById('create-modal');
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
});
