// SFDR Compliance Workspace Core State Management
const State = {
    currentView: 'dashboard', // dashboard, matrix, reviewer, settings
    projects: [],
    products: [],
    selectedProjectId: null,
    selectedProject: null,
    matrixItems: [],
    selectedMatrixItem: null,
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
    approveAnswer(answerId) { return this.fetch(`/api/answers/${answerId}/approve`, { method: 'POST' }); },
    rejectAnswer(answerId) { return this.fetch(`/api/answers/${answerId}/reject`, { method: 'POST' }); },
    
    getSettings() { return this.fetch('/api/settings'); },
    saveSettings(data) {
        return this.fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    }
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
    }
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
                <p style="margin-top: 10px;">Click "Create Project" above to start drafting your first SFDR RTS disclosure.</p>
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
    
    // Enable matrix navigation tab
    document.getElementById('nav-matrix').style.display = 'flex';
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

        // Render matrix rows
        const tbody = document.getElementById('matrix-table-body');
        tbody.innerHTML = '';

        State.matrixItems.forEach(item => {
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

            tbody.innerHTML += `
            <tr onclick="openReviewer('${item.field_id}')" style="cursor:pointer;">
                <td style="font-weight:600; color:#fff;">${item.field_label}</td>
                <td><code>${item.field_code}</code></td>
                <td>${item.annex_code || 'Annex I'}</td>
                <td><span class="badge ${statusBadge}">${item.answer_status}</span></td>
                <td><strong style="color:var(--accent-cyan);">${displayVal}</strong></td>
                <td style="max-width:200px;">${valIndicators}</td>
            </tr>`;
        });

    } finally {
        showLoader(false);
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
}

// --- Action Handlers ---

// Save edited draft
async function saveReviewerDraft() {
    if (!State.selectedMatrixItem) return;
    
    const text = document.getElementById('rev-editor-text').value;
    showLoader(true);
    try {
        await API.updateAnswer(State.selectedMatrixItem.answer_id, {
            answer_text: text,
            status: 'Draft'
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
        await API.approveAnswer(State.selectedMatrixItem.answer_id);
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
        await API.rejectAnswer(State.selectedMatrixItem.answer_id);
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
        }
        renderDashboard();
    } finally {
        showLoader(false);
    }
}

// Document Upload Flow
async function triggerDocUpload() {
    const fileInput = document.getElementById('doc-file-input');
    const sourceSelect = document.getElementById('doc-source-type');
    
    if (fileInput.files.length === 0) {
        alert("Please choose a file to upload.");
        return;
    }

    const file = fileInput.files[0];
    const source_type = sourceSelect.value;
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', source_type);

    showLoader(true);
    try {
        const res = await fetch(`/api/projects/${State.selectedProjectId}/documents`, {
            method: 'POST',
            body: formData
        });
        
        if (!res.ok) throw new Error("Upload failed.");
        
        fileInput.value = ''; // clear input
        await renderMatrix(); // reload matrix & documents list
        alert("Document ingested, parsed, and chunked successfully!");
    } catch (e) {
        alert(`Failed to upload: ${e.message}`);
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
window.addEventListener('load', () => {
    setView('dashboard');
    
    // Close modal on click overlay
    const modal = document.getElementById('create-modal');
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
});
