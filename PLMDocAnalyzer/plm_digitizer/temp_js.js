// ═══════════════════════════════════════════════════════════════
// MAIN APP STATE (Alpine.js root component)
// ═══════════════════════════════════════════════════════════════
function app() {
  return {
    currentPage: 'dashboard',
    theme: 'dark',
    toasts: [],
    toastId: 0,
    notifications: [],
    showNotifications: false,
    plmConnections: [],
    showAddConnModal: false,
    editingConn: null,
    testingConnId: null,
    connForm: { name:'', system_type:'aras', server_url:'', database_name:'', username:'', password:'', item_type:'Part' },
    connTestResultModal: null,
    testingConnModal: false,
    dashStats: {},
    heroStats: [],
    chartPeriod: 'daily',
    newRunResetKey: 0,
    activeRun: null,
    activeRunCount: 0,
    selectedRunId: null,
    historyRuns: [],
    historyTotal: 0,
    historyPage: 0,
    historySearch: '',
    historyStatus: '',
    expandedRunId: null,
    expandedRunLogs: {},
    activityChart: null,
    health: { redis: 'disconnected', openai: false },
    presets: [],

    navItems: [
      { page: 'dashboard',   label: 'Dashboard',        icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>' },
      { page: 'new-run',     label: 'New Run',          icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none"/></svg>' },
      { page: 'history',     label: 'Run History',      icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
      { page: 'results',     label: 'Results Explorer', icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>' },
      { page: 'connections', label: 'PLM Connections',  icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="3"/><circle cx="19" cy="5" r="2"/><circle cx="19" cy="19" r="2"/><line x1="11.5" y1="10.5" x2="17" y2="6.5"/><line x1="11.5" y1="13.5" x2="17" y2="17.5"/></svg>' },
      { page: 'settings',    label: 'Settings',         icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>' },
    ],

    get unreadNotifications() {
      return this.notifications.filter(n => !n.read).length;
    },

    async init() {
      // Load theme from settings
      const savedTheme = localStorage.getItem('plm_theme') || 'dark';
      this.theme = savedTheme;

      await this.loadDashboard();
      await this.loadConnections();
      await this.loadPresets();
      await this.checkHealth();
      this.pollActiveRuns();
    },

    navigate(page, runId = null) {
      this.currentPage = page;
      if (page === 'dashboard') this.loadDashboard();
      if (page === 'history') this.loadHistory();
      if (page === 'connections') this.loadConnections();
      if (page === 'results' && runId) {
        // Reset to null first so the $watch always fires even if same run ID
        this.selectedRunId = null;
        this.$nextTick(() => { this.selectedRunId = runId; });
      }
      // Reset the New Run wizard to step 1 whenever the user navigates to it fresh
      if (page === 'new-run') {
        this.newRunResetKey = (this.newRunResetKey || 0) + 1;
      }
    },

    // ─── Toast Notifications ──────────────────────────────────

    showToast(type, title, message, runId = null) {
      const id = ++this.toastId;
      this.toasts.push({ id, type, title, message });
      this.notifications.unshift({ id, type, title, message, timestamp: new Date().toISOString(), read: false, run_id: runId });
      setTimeout(() => this.removeToast(id), 5000);
    },

    removeToast(id) {
      this.toasts = this.toasts.filter(t => t.id !== id);
    },

    clearNotifications() {
      this.notifications = [];
      this.showNotifications = false;
    },

    // ─── API Helpers ──────────────────────────────────────────

    async api(method, path, body = null) {
      const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
      };
      if (body) opts.body = JSON.stringify(body);
      const resp = await fetch(path, opts);
      if (!resp.ok && resp.status !== 404) {
        const err = await resp.json().catch(() => ({ error: 'Request failed' }));
        throw new Error(err.error || 'Request failed');
      }
      return resp.json();
    },

    async get(path) { return this.api('GET', path); },
    async post(path, body) { return this.api('POST', path, body); },
    async del(path) { return this.api('DELETE', path); },
    async patch(path, body) { return this.api('PATCH', path, body); },

    // ─── Dashboard ────────────────────────────────────────────

    async loadDashboard() {
      try {
        const resp = await this.get('/api/dashboard/stats');
        if (resp.success) {
          this.dashStats = resp.data;
          this.heroStats = [
            { icon: '🏃', label: 'Total Runs', value: resp.data.total_runs, trend: 0 },
            { icon: '📁', label: 'Files Processed', value: resp.data.total_files_processed, trend: 0 },
            { icon: '✅', label: 'Pass Rate', value: (resp.data.overall_pass_rate ?? 0) + '%', trend: 0 },
            { icon: '📦', label: 'Records Extracted', value: resp.data.total_records_extracted, trend: 0 },
          ];
          this.activeRunCount = resp.data.active_runs || 0;
          this.$nextTick(() => this.renderChart(resp.data.daily_activity));
        }
      } catch (e) {
        console.error('Dashboard load failed:', e);
      }
    },

    renderChart(data) {
      const canvas = document.getElementById('activityChart');
      if (!canvas) return;

      const labels = data.map(d => {
        const date = new Date(d.date + 'T00:00:00');
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      });
      const passed = data.map(d => d.passed);
      const failed = data.map(d => d.failed);

      // If chart already exists and its canvas is still in the DOM, just update data
      if (this.activityChart && document.getElementById('activityChart')) {
        this.activityChart.data.labels = labels;
        this.activityChart.data.datasets[0].data = passed;
        this.activityChart.data.datasets[1].data = failed;
        this.activityChart.update('none'); // 'none' = skip animation on refresh
        return;
      }
      // Canvas was remounted (navigated away and back) — destroy stale instance
      if (this.activityChart) {
        try { this.activityChart.destroy(); } catch(_) {}
        this.activityChart = null;
      }

      // First-time creation — wait until the canvas has real dimensions
      if (!canvas.offsetParent || canvas.clientWidth === 0) {
        setTimeout(() => this.renderChart(data), 80);
        return;
      }

      const isLight = this.theme === 'light';
      const tickColor   = isLight ? '#5f6368' : '#9aa0a6';
      const gridColor   = isLight ? '#f1f3f4' : '#2d2d3f';
      const legendColor = isLight ? '#3c4043' : '#9aa0a6';

      this.activityChart = new Chart(canvas, {
        type: 'line',
        data: {
          labels,
          datasets: [
            {
              label: 'Passed',
              data: passed,
              borderColor: isLight ? '#1e8e3e' : '#34a853',
              backgroundColor: isLight ? 'rgba(30,142,62,0.08)' : 'rgba(52,168,83,0.1)',
              tension: 0.4, fill: true, pointRadius: 3,
              pointBackgroundColor: isLight ? '#1e8e3e' : '#34a853',
            },
            {
              label: 'Failed',
              data: failed,
              borderColor: isLight ? '#d93025' : '#ea4335',
              backgroundColor: isLight ? 'rgba(217,48,37,0.07)' : 'rgba(234,67,53,0.1)',
              tension: 0.4, fill: true, pointRadius: 3,
              pointBackgroundColor: isLight ? '#d93025' : '#ea4335',
            },
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 400 },
          plugins: {
            legend: { labels: { color: legendColor, boxWidth: 10, font: { family: 'Roboto', size: 12 } } }
          },
          scales: {
            x: { ticks: { color: tickColor, maxTicksLimit: 10, font: { family: 'Roboto', size: 11 } }, grid: { color: gridColor } },
            y: { beginAtZero: true, ticks: { color: tickColor, font: { family: 'Roboto', size: 11 }, precision: 0 }, grid: { color: gridColor } }
          }
        }
      });
    },

    updateChart() {
      this.loadDashboard();
    },

    // ─── Health Check ─────────────────────────────────────────

    async checkHealth() {
      try {
        const resp = await this.get('/api/health');
        if (resp.success) {
          const rs = resp.data.redis?.status;
          this.health.redis = rs === 'connected' ? 'connected'
                            : rs === 'not_configured' ? 'not_configured'
                            : 'disconnected';
        }
        // Check if any LLM key is configured
        const settingsResp = await this.get('/api/settings');
        if (settingsResp.success) {
          const d = settingsResp.data;
          this.health.openai = ('openai_api_key' in d) || ('azure_api_key' in d) || d.llm_provider === 'ollama';
          // Restore provider preference for other components
          if (d.llm_provider) this.llmProvider = d.llm_provider;
        }
      } catch (e) {}
    },

    // ─── Active Run Polling ───────────────────────────────────

    async pollActiveRuns() {
      setInterval(async () => {
        if (this.currentPage === 'dashboard') {
          await this.loadDashboard();
        }
        // Check for active runs
        const resp = await this.get('/api/runs?status=running&limit=1').catch(() => null);
        if (resp?.success && resp.data.runs.length > 0) {
          const run = resp.data.runs[0];
          this.activeRun = {
            id: run.id, name: run.name,
            processed: run.processed_files, total: run.total_files,
            passed: run.passed_records, failed: run.failed_records,
            rate: null, eta: null, currentFile: null,
          };
          this.activeRunCount = resp.data.total;
        } else {
          this.activeRunCount = 0;
          if (this.activeRun) {
            this.activeRun = null;
            await this.loadDashboard();
          }
        }
      }, 5000);
    },

    // ─── Run Actions ──────────────────────────────────────────

    async cancelRun(runId) {
      if (!confirm('Cancel this run?')) return;
      const resp = await this.del(`/api/runs/${runId}`);
      if (resp.success) {
        this.showToast('info', 'Run Cancelled', 'The run has been cancelled');
        await this.loadDashboard();
      }
    },

    async downloadOutput(runId) {
      if (!runId) return;
      window.location = `/api/runs/${runId}/download`;
    },

    async reprocessRun(runId) {
      const resp = await this.post(`/api/runs/${runId}/reprocess`, {});
      if (resp.success) {
        this.showToast('success', 'Re-run Started', 'New run created with same configuration');
        await this.loadDashboard();
      }
    },

    // ─── History ──────────────────────────────────────────────

    async loadHistory() {
      try {
        const params = new URLSearchParams({
          limit: 50,
          offset: this.historyPage * 50,
        });
        if (this.historySearch) params.set('search', this.historySearch);
        if (this.historyStatus) params.set('status', this.historyStatus);

        const resp = await this.get(`/api/runs?${params}`);
        if (resp.success) {
          this.historyRuns = resp.data.runs;
          this.historyTotal = resp.data.total;
        }
      } catch (e) {
        console.error('History load failed:', e);
      }
    },

    async toggleExpandRun(runId) {
      if (this.expandedRunId === runId) {
        this.expandedRunId = null;
        return;
      }
      this.expandedRunId = runId;
      // Load logs
      try {
        const resp = await this.get(`/api/runs/${runId}/logs?limit=5`);
        if (resp.success) {
          this.expandedRunLogs[runId] = resp.data.logs;
        }
      } catch (e) {}
    },

    // ─── PLM Connections ──────────────────────────────────────

    async loadConnections() {
      const resp = await this.get('/api/connections');
      if (resp.success) this.plmConnections = resp.data;
    },

    async testConnection(id) {
      this.testingConnId = id;
      try {
        const resp = await this.post(`/api/connections/${id}/test`, {});
        const conn = this.plmConnections.find(c => c.id === id);
        if (conn) {
          conn.test_status = resp.success ? 'success' : 'failed';
          conn.test_message = resp.data?.message || resp.error;
          conn.last_tested_at = new Date().toISOString();
        }
        this.showToast(resp.success ? 'success' : 'error', 'Connection Test', resp.data?.message || resp.error);
      } catch (e) {
        this.showToast('error', 'Connection Test Failed', e.message);
      }
      this.testingConnId = null;
    },

    async deleteConnection(id) {
      if (!confirm('Delete this connection?')) return;
      await this.del(`/api/connections/${id}`);
      this.plmConnections = this.plmConnections.filter(c => c.id !== id);
      this.showToast('info', 'Connection Deleted', '');
    },

    editConnection(conn) {
      this.editingConn = conn;
      this.connForm = { ...conn, password: '' };
      this.connTestResultModal = null;
      this.showAddConnModal = true;
    },

    async testConnectionModal() {
      this.testingConnModal = true;
      try {
        const resp = await this.post('/api/validate/aras', this.connForm);
        this.connTestResultModal = { success: resp.success, message: resp.data?.message || resp.error };
      } catch (e) {
        this.connTestResultModal = { success: false, message: e.message };
      }
      this.testingConnModal = false;
    },

    async saveConnection() {
      try {
        let resp;
        if (this.editingConn) {
          resp = await this.api('PUT', `/api/connections/${this.editingConn.id}`, this.connForm);
        } else {
          resp = await this.post('/api/connections', this.connForm);
        }
        if (resp.success) {
          await this.loadConnections();
          this.showAddConnModal = false;
          this.editingConn = null;
          this.connTestResultModal = null;
          this.connForm = { name:'', system_type:'aras', server_url:'', database_name:'', username:'', password:'', item_type:'Part' };
          this.showToast('success', 'Connection Saved', '');
        } else {
          this.showToast('error', 'Save Failed', resp.error);
        }
      } catch (e) {
        this.showToast('error', 'Save Failed', e.message);
      }
    },

    // ─── Presets ──────────────────────────────────────────────

    async loadPresets() {
      try {
        const resp = await fetch('/api/presets').then(r => r.json());
        if (resp.success) this.presets = resp.data || [];
      } catch (e) {
        this.presets = [];
      }
    },

    // ─── Formatters ───────────────────────────────────────────

    formatNumber(n) {
      if (n === null || n === undefined) return '0';
      // If value is already a formatted string (e.g. "92.5%"), return as-is
      if (typeof n === 'string' && isNaN(Number(n))) return n;
      return Number(n).toLocaleString();
    },

    formatDate(dt) {
      if (!dt) return '—';
      return new Date(dt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    },

    formatTime(dt) {
      if (!dt) return '';
      const d = new Date(dt);
      const now = new Date();
      const diff = (now - d) / 1000;
      if (diff < 60) return 'Just now';
      if (diff < 3600) return Math.floor(diff/60) + 'm ago';
      if (diff < 86400) return Math.floor(diff/3600) + 'h ago';
      return d.toLocaleDateString();
    },

    formatDuration(secs) {
      if (!secs) return '—';
      if (secs < 60) return secs.toFixed(0) + 's';
      if (secs < 3600) return (secs/60).toFixed(1) + 'm';
      return (secs/3600).toFixed(1) + 'h';
    },

    statusBadgeClass(status) {
      const light = {
        'running':   'badge-info-light',
        'completed': 'badge-success-light',
        'failed':    'badge-error-light',
        'pending':   'badge-neutral-light',
        'cancelled': 'badge-warn-light',
      };
      const dark = {
        'running':   'badge-info-dark',
        'completed': 'badge-success-dark',
        'failed':    'badge-error-dark',
        'pending':   'badge-neutral-dark',
        'cancelled': 'badge-warn-dark',
      };
      const map = this.$root?.theme === 'light' ? light : dark;
      return map[status] || (this.$root?.theme === 'light' ? 'badge-neutral-light' : 'badge-neutral-dark');
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// NEW RUN WIZARD
// ═══════════════════════════════════════════════════════════════
function newRunWizard() {
  return {
    currentStep: 1,
    steps: ['Source', 'Fields', 'Output', 'PLM Target', 'Review'],
    llmProvider: 'openai',  // loaded from settings in init()
    get llmModels() {
      const models = {
        openai: [
          { id: 'gpt-4o',        name: 'GPT-4o',        speed: 'Fast',      cost: '0.005',    recommended: false },
          { id: 'gpt-4o-mini',   name: 'GPT-4o Mini',   speed: 'Very Fast', cost: '0.00015',  recommended: true  },
          { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', speed: 'Fastest',   cost: '0.0005',   recommended: false },
        ],
        azure: [],  // Azure uses a text input (deployment name = model) — handled in template
        ollama: [
          { id: 'qwen2.5:7b',        name: 'Qwen 2.5 7B',       speed: 'Fast',    cost: 'Free (local)', recommended: true  },
          { id: 'qwen2.5:14b',       name: 'Qwen 2.5 14B',      speed: 'Medium',  cost: 'Free (local)', recommended: false },
          { id: 'qwen2.5:32b',       name: 'Qwen 2.5 32B',      speed: 'Slow',    cost: 'Free (local)', recommended: false },
          { id: 'qwen2.5-coder:7b',  name: 'Qwen 2.5 Coder 7B', speed: 'Fast',    cost: 'Free (local)', recommended: false },
          { id: 'llama3.2:3b',       name: 'Llama 3.2 3B',      speed: 'Fastest', cost: 'Free (local)', recommended: false },
          { id: 'llama3.1:8b',       name: 'Llama 3.1 8B',      speed: 'Fast',    cost: 'Free (local)', recommended: false },
          { id: 'mistral:7b',        name: 'Mistral 7B',         speed: 'Fast',    cost: 'Free (local)', recommended: false },
        ],
      };
      return models[this.llmProvider] || models.openai;
    },
    config: {
      name: '',
      folder_path: '',
      output_fields: [],
      output_format: 'excel',
      output_file_path: '',
      llm_model: 'gpt-4o-mini',
      worker_count: 4,
      batch_size: 10,
      confidence_threshold: 0.7,
      plm_connection_id: '',
      auto_push: false,
    },
    fieldsInput: '',
    customField: '',
    suggestedFields: [],
    suggestingFields: false,
    folderInfo: null,
    validatingFolder: false,
    presetName: '',
    launching: false,
    runLaunched: false,
    viewingRunId: null,
    ws: null,
    liveLogs: [],
    recentFiles: [],
    liveProgress: 0,
    liveCurrentFile: '',
    runStats: [],
    runProgress: {},
    runStatus: null,
    termAutoScroll: true,
    showPushModal: false,
    pushConnectionId: '',
    pipelineStages: [
      { label: '1 · Discover', state: 'pending' },
      { label: '2 · Extract', state: 'pending' },
      { label: '3 · LLM', state: 'pending' },
      { label: '4 · Write Output', state: 'pending' },
      { label: '5 · Complete', state: 'pending' },
    ],
    newConn: { name:'', system_type:'aras', server_url:'', database_name:'', username:'', password:'', item_type:'Part' },
    testingConn: false,
    connTestResult: null,

    resetWizard() {
      // Close any open WebSocket
      if (this.ws) { try { this.ws.close(); } catch(_){} this.ws = null; }
      this.runLaunched = false;
      this.viewingRunId = null;
      this.currentStep = 1;
      this.launching = false;
      this.runStatus = null;
      this.liveLogs = [];
      this.recentFiles = [];
      this.liveProgress = 0;
      this.liveCurrentFile = '';
      this.runProgress = {};
      this.runStats = this.buildRunStats({});
      this.pipelineStages = this.pipelineStages.map(s => ({ ...s, state: 'pending' }));
      // Reset run name to today
      const now = new Date();
      this.config.name = 'Run ' + now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    },

    async init() {
      // Auto-fill name
      const now = new Date();
      this.config.name = 'Run ' + now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
      // Watch for reset signal from parent navigate()
      this.$watch('$root.newRunResetKey', () => this.resetWizard());
      // Load settings for defaults
      try {
        const resp = await fetch('/api/settings').then(r => r.json());
        if (resp.success) {
          const d = resp.data;
          // Set active provider so model list updates
          if (d.llm_provider) this.llmProvider = d.llm_provider;
          // Set default model based on provider
          if (d.llm_provider === 'ollama') {
            this.config.llm_model = d.ollama_model || d.default_model || 'qwen2.5:7b';
          } else if (d.llm_provider === 'azure') {
            this.config.llm_model = d.azure_deployment || d.default_model || '';
          } else {
            this.config.llm_model = d.default_model || 'gpt-4o-mini';
          }
          if (d.default_workers)    this.config.worker_count  = parseInt(d.default_workers);
          if (d.default_batch_size) this.config.batch_size    = parseInt(d.default_batch_size);
          if (d.default_format)     this.config.output_format = d.default_format;
        }
      } catch (e) {}
      this.runStats = this.buildRunStats({});
    },

    buildRunStats(p) {
      const lt = this.theme === 'light';
      return [
        { label: 'Processed', value: p.processed || 0, color: lt ? 'text-[#1a73e8]' : 'text-[#8ab4f8]' },
        { label: 'Passed',    value: p.passed    || 0, color: lt ? 'text-[#137333]' : 'text-[#81c995]' },
        { label: 'Failed',    value: p.failed    || 0, color: lt ? 'text-[#c5221f]' : 'text-[#f28b82]' },
        { label: 'Skipped',  value: p.skipped   || 0, color: lt ? 'text-[#b06000]' : 'text-[#fdd663]' },
        { label: 'Rate',     value: p.rate  || '—',   color: lt ? 'text-[#1a73e8]' : 'text-[#8ab4f8]' },
        { label: 'ETA',      value: p.eta   || '—',   color: lt ? 'text-[#5f6368]' : 'text-[#9aa0a6]' },
      ];
    },

    canAdvance() {
      if (this.currentStep === 1) return !!this.config.folder_path;
      if (this.currentStep === 2) return this.config.output_fields.length > 0;
      if (this.currentStep === 3) return !!this.config.name;
      return true;
    },

    nextStep() {
      if (!this.canAdvance()) return;
      if (this.currentStep < 5) this.currentStep++;
    },

    parseFields() {
      if (!this.fieldsInput.trim()) { this.config.output_fields = []; return; }
      const fields = this.fieldsInput.split(',').map(f => f.trim()).filter(Boolean);
      const unique = [...new Set(fields)];
      this.config.output_fields = unique;
    },

    removeField(i) {
      this.config.output_fields.splice(i, 1);
      this.fieldsInput = this.config.output_fields.join(', ');
    },

    addCustomField() {
      const f = this.customField.trim();
      if (f && !this.config.output_fields.includes(f)) {
        this.config.output_fields.push(f);
        this.fieldsInput = this.config.output_fields.join(', ');
      }
      this.customField = '';
    },

    addSuggestedField(field) {
      if (!this.config.output_fields.includes(field)) {
        this.config.output_fields.push(field);
        this.fieldsInput = this.config.output_fields.join(', ');
        this.suggestedFields = this.suggestedFields.filter(f => f !== field);
      }
    },

    async suggestFields() {
      this.suggestingFields = true;
      try {
        const fileTypes = this.folderInfo ? Object.keys(this.folderInfo.file_breakdown) : [];
        const resp = await fetch('/api/suggest/fields', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ current_fields: this.config.output_fields, file_types: fileTypes }),
        }).then(r => r.json());
        if (resp.success) this.suggestedFields = resp.data || [];
      } catch (e) {}
      this.suggestingFields = false;
    },

    async validateFolder() {
      if (!this.config.folder_path) return;
      this.validatingFolder = true;
      try {
        const resp = await fetch('/api/validate/folder', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ folder_path: this.config.folder_path }),
        }).then(r => r.json());
        this.folderInfo = resp.data;
        if (!this.config.name || this.config.name.startsWith('Run ')) {
          const parts = this.config.folder_path.replace(/\\/g, '/').split('/');
          const folderName = parts[parts.length - 1] || parts[parts.length - 2] || 'Run';
          const date = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
          this.config.name = folderName + ' — ' + date;
        }
      } catch (e) {}
      this.validatingFolder = false;
    },

    fileTypeIcon(type) {
      const icons = { PDF:'<span class="text-red-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', DOCX:'<span class="text-blue-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', DOC:'<span class="text-blue-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', XLSX:'<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>', XLS:'<svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>', PNG:'<span class="text-purple-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', JPG:'<span class="text-purple-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', JPEG:'<span class="text-purple-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', TIFF:'<span class="text-purple-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', BMP:'<span class="text-purple-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', CSV:'<span class="text-green-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>', TXT:'<span class="text-gray-400"><svg class="w-4 h-4 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>' };
      return icons[type] || '📁';
    },

    async testAndSaveConnection() {
      this.testingConn = true;
      try {
        const resp = await fetch('/api/validate/aras', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.newConn),
        }).then(r => r.json());
        this.connTestResult = resp;
        if (resp.success) {
          const saveResp = await fetch('/api/connections', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(this.newConn),
          }).then(r => r.json());
          if (saveResp.success) {
            const conns = await fetch('/api/connections').then(r => r.json());
            if (conns.success) this.$root.plmConnections = conns.data;
            const newId = saveResp.data?.id;
            if (newId) this.config.plm_connection_id = newId;
          }
        }
      } catch (e) { this.connTestResult = { success: false, message: e.message }; }
      this.testingConn = false;
    },

    async savePreset() {
      if (!this.presetName.trim()) return;
      try {
        await fetch('/api/presets', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: this.presetName, config: this.config }),
        });
        const name = this.presetName;
        this.presetName = '';
        await this.loadPresets();   // reload into local this.presets
        this.$root.showToast('success', 'Preset saved', name);
      } catch (e) {
        this.$root.showToast('error', 'Save failed', e.message);
      }
    },

    loadPreset(presetId) {
      if (!presetId) return;
      const preset = this.presets.find(p => p.id === presetId);
      if (!preset) {
        this.$root.showToast('error', 'Preset not found', 'Could not load the selected preset');
        return;
      }
      const cfg = typeof preset.config === 'string' ? JSON.parse(preset.config) : preset.config;
      this.config = { ...this.config, ...cfg };
      this.fieldsInput = (cfg.output_fields || []).join(', ');
      this.$root.showToast('success', 'Preset loaded', preset.name);
      // Reset select back to placeholder so same preset can be re-selected
      this.$nextTick(() => {
        const sel = document.querySelector('select[x-ref="presetSelect"]');
        if (sel) sel.value = '';
      });
    },

    async launchRun() {
      this.launching = true;
      try {
        const payload = { ...this.config };
        if (!payload.output_file_path) delete payload.output_file_path;
        if (!payload.plm_connection_id || payload.plm_connection_id === '__new__') delete payload.plm_connection_id;

        const resp = await fetch('/api/runs', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        }).then(r => r.json());

        if (resp.success) {
          this.viewingRunId = resp.data.id;
          this.runLaunched = true;
          this.runStatus = 'running';
          this.liveProgress = 0;
          this.liveLogs = [];
          this.recentFiles = [];
          this.runProgress = {};
          this.termAutoScroll = true;
          this.pipelineStages = [
            { label: '1 · Discover', state: 'pending' },
            { label: '2 · Extract', state: 'pending' },
            { label: '3 · LLM', state: 'pending' },
            { label: '4 · Write Output', state: 'pending' },
            { label: '5 · Complete', state: 'pending' },
          ];
          this.connectWebSocket(resp.data.id);
          this.$root.showToast('success', 'Run Launched!', resp.data.name);
        } else {
          this.$root.showToast('error', 'Launch Failed', resp.error);
        }
      } catch (e) {
        this.$root.showToast('error', 'Launch Failed', e.message);
      }
      this.launching = false;
    },

    connectWebSocket(runId) {
      if (this.ws) this.ws.close();
      const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${proto}//${location.host}/ws/runs/${runId}`;
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this._termLog('info', 'WebSocket connected — waiting for events…');
      };

      this.ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);

        if (msg.event === 'ping') return;

        if (msg.event === 'progress') {
          this.runProgress = msg;
          const total = msg.total || 1;
          this.liveProgress = Math.round((msg.processed / total) * 100);
          this.liveCurrentFile = msg.current_file || '';
          this.runStats = this.buildRunStats(msg);
          // Advance pipeline stages based on progress
          this._advanceStages(msg);
          // Add a file entry to the feed
          if (msg.current_file) {
            // We don't know pass/fail from progress alone — mark as processing
            // Real file results come from the log messages
          }
        } else if (msg.event === 'log') {
          if (!msg.timestamp) msg.timestamp = new Date().toISOString();
          this.liveLogs.push(msg);
          // Parse log messages to drive stage + file feed
          this._parseLogForStages(msg.message);
          // Populate file feed from per-file log lines
          this._parseLogForFileFeed(msg);
          this._scrollTerminal();
        } else if (msg.event === 'file_result') {
          // If backend emits file_result events
          this.recentFiles.push(msg);
        } else if (msg.event === 'completed') {
          this.runStatus = 'completed';
          this.liveProgress = 100;
          this._setAllStagesDone();
          if (msg.summary) {
            this.runProgress = { ...this.runProgress, ...msg.summary };
            this.runStats = this.buildRunStats(msg.summary);
          }
          // Choose colour and message based on actual pass/fail outcome
          const passCount = msg.pass_count ?? (msg.summary?.passed_records ?? 0);
          const failCount = msg.fail_count ?? (msg.summary?.failed_records ?? 0);
          const total = passCount + failCount;
          if (total === 0 || passCount === 0) {
            this._termLog('error', `✗ Process exited — 0 files passed. See errors above for details.`);
            this.$root.showToast('error', 'Run Completed with Failures',
              failCount > 0
                ? `All ${failCount} file(s) failed. Check the terminal for the error reason.`
                : 'No files were processed.');
          } else if (failCount === 0) {
            this._termLog('success', `✓ Process exited with code 0 — all ${passCount} file(s) passed`);
            this.$root.showToast('success', 'Run Completed!', `${passCount} file(s) extracted successfully. Click Download for your output.`);
          } else {
            const pct = Math.round(passCount / total * 100);
            this._termLog('warning', `⚠ Process exited — ${passCount}/${total} passed (${pct}%). ${failCount} failed.`);
            this.$root.showToast('warning', 'Run Completed with Partial Results',
              `${passCount} passed, ${failCount} failed. Download contains partial results.`);
          }
          this._scrollTerminal();
          this.$root.loadDashboard();
        } else if (msg.event === 'error') {
          this.runStatus = 'failed';
          this._termLog('error', '✗ ' + (msg.message || 'Unknown error'));
          this._scrollTerminal();
          this.$root.showToast('error', 'Run Failed', msg.message);
        } else if (msg.event === 'state') {
          if (msg.run) {
            const r = msg.run;
            const total = r.total || 1;
            this.liveProgress = Math.round((r.processed / total) * 100);
            this.runProgress = { ...this.runProgress, processed: r.processed, total: r.total, passed: r.passed, failed: r.failed, skipped: r.skipped };
            this.runStats = this.buildRunStats(r);
            if (r.status === 'completed') { this.runStatus = 'completed'; this._setAllStagesDone(); }
            if (r.status === 'failed') this.runStatus = 'failed';
            if (r.status === 'cancelled') this.runStatus = 'cancelled';
          }
        }
      };

      this.ws.onclose = () => {
        if (this.runStatus === 'running') {
          this._termLog('warning', 'Connection lost — reconnecting in 3s…');
          setTimeout(() => this.connectWebSocket(runId), 3000);
        }
      };

      this.ws.onerror = (err) => {
        this._termLog('error', 'WebSocket error');
      };
    },

    // ── Terminal helpers ──────────────────────────────────────────
    _termLog(level, message) {
      this.liveLogs.push({ level, message, timestamp: new Date().toISOString() });
      this._scrollTerminal();
    },

    _scrollTerminal() {
      if (!this.termAutoScroll) return;
      this.$nextTick(() => {
        const el = this.$refs?.logContainer;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },

    // Drive pipeline stage highlights from log message content
    _parseLogForStages(msg) {
      if (!msg) return;
      const m = msg.toLowerCase();
      if (m.includes('stage 1') || m.includes('discover')) {
        this._setStage(0, 'active');
      } else if (m.includes('stage 2') || m.includes('extract') || m.includes('processing')) {
        this._setStage(0, 'done'); this._setStage(1, 'active');
      } else if (m.includes('stage 3') || m.includes('llm') || m.includes('batch')) {
        this._setStage(1, 'done'); this._setStage(2, 'active');
      } else if (m.includes('stage 4') || m.includes('output') || m.includes('writing')) {
        this._setStage(2, 'done'); this._setStage(3, 'active');
      } else if (m.includes('completed') || m.includes('run completed')) {
        this._setAllStagesDone();
      }
      // Capture file results from log if backend doesn't send file_result events
      if (msg.includes('✓') || m.includes('passed') || m.includes('failed')) {
        // Rough heuristic — real data comes from progress events
      }
    },

    // Populate the file feed from per-file log messages emitted by the worker
    _parseLogForFileFeed(msg) {
      const m = msg.message || '';
      // Lines like "  ✓ Invoice.pdf — confidence 87% — Part Number: 123"
      // Lines like "  ✗ Invoice.pdf — Low confidence (45%)"
      // Lines like "  📄 Extracted Invoice.pdf via pdfplumber (2,340 chars)"
      const passMatch = m.match(/✓\s+(.+?)\s+—/);
      const failMatch = m.match(/✗\s+(.+?)\s+—/);
      const extractMatch = m.match(/📄\s+Extracted\s+(.+?)\s+via/);

      if (passMatch) {
        const fname = passMatch[1].trim();
        // Extract confidence if present
        const confMatch = m.match(/confidence\s+([\d.]+)%/i);
        const conf = confMatch ? parseFloat(confMatch[1]) / 100 : undefined;
        // Replace existing entry for this file, or add new
        const idx = this.recentFiles.findIndex(f => f.file_path?.endsWith(fname));
        const entry = { file_path: fname, status: 'passed', confidence: conf };
        if (idx >= 0) this.recentFiles[idx] = entry;
        else this.recentFiles.push(entry);
      } else if (failMatch) {
        const fname = failMatch[1].trim();
        const idx = this.recentFiles.findIndex(f => f.file_path?.endsWith(fname));
        const entry = { file_path: fname, status: 'failed', confidence: 0 };
        if (idx >= 0) this.recentFiles[idx] = entry;
        else this.recentFiles.push(entry);
      } else if (extractMatch) {
        const fname = extractMatch[1].trim();
        // Add as "processing" if not already in feed
        if (!this.recentFiles.find(f => f.file_path?.endsWith(fname))) {
          this.recentFiles.push({ file_path: fname, status: 'processing', confidence: undefined });
        }
      }
    },

    _advanceStages(progress) {
      const pct = this.liveProgress;
      if (pct > 0)  this._setStage(0, 'done');
      if (pct > 5)  { this._setStage(1, 'active'); }
      if (pct > 15) { this._setStage(1, 'done'); this._setStage(2, 'active'); }
      if (pct > 85) { this._setStage(2, 'done'); this._setStage(3, 'active'); }
      // Also push file entries from progress events
      if (progress.current_file && progress.processed > 0) {
        // We infer last file status from overall pass/fail delta
        const lastStatus = (this.runProgress.passed || 0) >= (progress.passed || 0) ? 'failed' : 'passed';
        if (this.recentFiles.length < progress.processed) {
          this.recentFiles.push({
            file_path: progress.current_file,
            status: 'processing',
            confidence: undefined,
          });
        }
      }
    },

    _setStage(idx, state) {
      if (this.pipelineStages[idx] && this.pipelineStages[idx].state !== 'done') {
        this.pipelineStages[idx].state = state;
      }
    },

    _setAllStagesDone() {
      this.pipelineStages.forEach(s => s.state = 'done');
    },

    async executePush() {
      if (!this.pushConnectionId) return;
      const resp = await fetch(`/api/runs/${this.viewingRunId}/push`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ connection_id: this.pushConnectionId }),
      }).then(r => r.json());
      if (resp.success) {
        this.$root.showToast('success', 'Push Started', 'Pushing records to PLM...');
        this.showPushModal = false;
      } else {
        this.$root.showToast('error', 'Push Failed', resp.error);
      }
    },

    formatLogTime(ts) {
      const d = ts ? new Date(ts) : new Date();
      return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// RESULTS EXPLORER
// ═══════════════════════════════════════════════════════════════
function resultsExplorer() {
  return {
    selectedRunId: null,
    resultsTab: 'all',
    results: [],
    resultsTotal: 0,
    resultsPage: 0,
    resultsSearch: '',
    selectedDetail: null,
    editingResult: false,
    selectedResults: [],
    allRuns: [],
    editedData: {},
    runSummary: null,     // full run object for the selected run

    async init() {
      // Inherit selectedRunId from parent if set
      const parentRunId = this.$root?.selectedRunId;
      if (parentRunId) this.selectedRunId = parentRunId;
      await this.loadAllRuns();
      if (this.selectedRunId) {
        await this.loadRunSummary();
        await this.loadResults();
      }

      // Watch parent selectedRunId so Results button navigation works
      // even after this component has already been initialised
      this.$watch('$root.selectedRunId', async (newId) => {
        if (newId && newId !== this.selectedRunId) {
          this.selectedRunId = newId;
          this.resultsPage = 0;
          this.resultsTab = 'all';
          this.selectedDetail = null;
          this.runSummary = null;
          await this.loadAllRuns();
          await this.loadRunSummary();
          await this.loadResults();
        }
      });
    },

    async onRunChange() {
      this.resultsPage = 0;
      this.resultsTab = 'all';
      this.selectedDetail = null;
      this.runSummary = null;
      this.results = [];
      if (this.selectedRunId) {
        await this.loadRunSummary();
        await this.loadResults();
      }
    },

    async loadAllRuns() {
      const resp = await fetch('/api/runs?limit=200').then(r => r.json());
      if (resp.success) this.allRuns = resp.data.runs;
    },

    async loadRunSummary() {
      if (!this.selectedRunId) return;
      try {
        const resp = await fetch(`/api/runs/${this.selectedRunId}`).then(r => r.json());
        if (resp.success) this.runSummary = resp.data;
      } catch(e) {}
    },

    async loadResults() {
      if (!this.selectedRunId) return;
      const params = new URLSearchParams({ limit: 50, offset: this.resultsPage * 50 });
      if (this.resultsTab !== 'all') params.set('status', this.resultsTab);
      if (this.resultsSearch) params.set('search', this.resultsSearch);

      const resp = await fetch(`/api/runs/${this.selectedRunId}/results?${params}`).then(r => r.json());
      if (resp.success) {
        this.results = resp.data.results;
        this.resultsTotal = resp.data.total;
      }
    },

    formatDur(secs) {
      if (!secs) return '—';
      if (secs < 60) return Math.round(secs) + 's';
      if (secs < 3600) return (secs / 60).toFixed(1) + 'm';
      return (secs / 3600).toFixed(1) + 'h';
    },

    downloadRun() {
      if (!this.selectedRunId) return;
      window.location.href = `/api/runs/${this.selectedRunId}/download`;
    },

    exportAll() {
      // Export all currently loaded results as CSV
      if (!this.results.length) {
        this.$root.showToast('warning', 'No data', 'No results loaded to export');
        return;
      }
      // Collect all extracted_data keys
      const allKeys = [...new Set(this.results.flatMap(r => Object.keys(r.extracted_data || {})))];
      const headers = ['File', 'Type', 'Status', 'Confidence', ...allKeys];
      const rows = this.results.map(r => [
        r.file_path,
        r.file_type || '',
        r.status,
        r.confidence_score !== null ? (r.confidence_score * 100).toFixed(1) + '%' : '',
        ...allKeys.map(k => {
          const v = (r.extracted_data || {})[k];
          // Escape commas and quotes for CSV
          if (v === null || v === undefined) return '';
          const str = String(v);
          return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
        }),
      ]);
      const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `results_${this.selectedRunId}_${this.resultsTab}.csv`;
      a.click();
      this.$root.showToast('success', 'Export ready', `${rows.length} rows exported to CSV`);
    },

    toggleSelectAll(e) {
      this.selectedResults = e.target.checked ? this.results.map(r => r.id) : [];
    },

    exportSelected() {
      const selected = this.results.filter(r => this.selectedResults.includes(r.id));
      if (!selected.length) return;
      const allKeys = [...new Set(selected.flatMap(r => Object.keys(r.extracted_data || {})))];
      const headers = ['File', 'Type', 'Status', 'Confidence', ...allKeys];
      const rows = selected.map(r => [
        r.file_path, r.file_type || '', r.status,
        r.confidence_score !== null ? (r.confidence_score * 100).toFixed(1) + '%' : '',
        ...allKeys.map(k => {
          const v = (r.extracted_data || {})[k];
          if (v === null || v === undefined) return '';
          const str = String(v);
          return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
        }),
      ]);
      const csv = [headers, ...rows].map(r => r.join(',')).join('\n');
      const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'selected_results.csv';
      a.click();
      this.$root.showToast('success', 'Export ready', `${rows.length} selected rows exported`);
    },

    updateField(key, value) {
      if (!this.editedData) this.editedData = {};
      this.editedData[key] = value;
    },

    async saveResultEdit() {
      if (!this.selectedDetail) return;
      const newData = { ...this.selectedDetail.extracted_data, ...this.editedData };
      const resp = await fetch(`/api/runs/${this.selectedRunId}/results/${this.selectedDetail.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ extracted_data: newData, manually_edited: true }),
      }).then(r => r.json());
      if (resp.success) {
        this.selectedDetail.extracted_data = newData;
        this.selectedDetail.manually_edited = true;
        this.editingResult = false;
        this.editedData = {};
        this.$root.showToast('success', 'Saved', 'Extracted data updated');
      }
    },
  };
}

// ═══════════════════════════════════════════════════════════════
// SETTINGS PAGE
// ═══════════════════════════════════════════════════════════════
function settingsPage() {
  return {
    activeTab: 'llm',
    settingsTabs: [
      { id: 'llm',         label: 'LLM',          icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>' },
      { id: 'performance', label: 'Performance',  icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>' },
      { id: 'output',      label: 'Output',       icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>' },
      { id: 'appearance',  label: 'Appearance',   icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>' },
      { id: 'about',       label: 'Audit & Help', icon: '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>' },
    ],
    settings: {
      llm_provider: 'openai',
      openai_api_key: '',
      azure_api_key: '',
      azure_endpoint: '',
      azure_deployment: '',
      azure_api_version: '2024-10-21',
      ollama_base_url: 'http://localhost:11434',
      ollama_model: 'qwen2.5:7b',
      default_model: 'gpt-4o-mini',
      default_workers: 4,
      default_batch_size: 10,
      confidence_threshold: 0.7,
      max_file_size_mb: 100,
      ocr_language: 'eng',
      default_output_folder: '',
      default_format: 'excel',
      table_density: 'comfortable',
    },
    showApiKey: false,
    savingKey: false,
    validatingKey: false,
    keyValidationResult: null,
    costEstimatorCount: 1000,
    auditEntries: [],
    quickStartSteps: [
      { title: 'Choose LLM Provider', desc: 'Go to Settings > LLM and choose OpenAI, Azure OpenAI, or Ollama (local/free). Enter your credentials and test the connection.' },
      { title: 'Start a New Run', desc: 'Click New Run in the sidebar, configure your folder and output fields' },
      { title: 'Define Output Fields', desc: 'Enter the data fields you want to extract from your documents' },
      { title: 'Launch and Monitor', desc: 'Watch real-time progress as your documents are processed' },
      { title: 'Review and Download', desc: 'Use Results Explorer to review extractions, then download your output file' },
      { title: 'Push to PLM', desc: 'Configure a PLM connection and push verified records to your PLM system' },
    ],

    async init() {
      await this.loadSettings();
      await this.loadAuditLog();
    },

    async loadSettings() {
      const resp = await fetch('/api/settings').then(r => r.json());
      if (resp.success) {
        Object.assign(this.settings, resp.data);
        // Ensure provider defaults to openai if not saved yet
        if (!this.settings.llm_provider) this.settings.llm_provider = 'openai';
      }
    },

    async setProvider(provider) {
      this.settings.llm_provider = provider;
      this.keyValidationResult = null;
      // Set sensible default model when switching provider
      if (provider === 'ollama' && !['qwen2.5:7b','qwen2.5:14b','qwen2.5:32b','qwen2.5-coder:7b','llama3.2:3b','llama3.1:8b','mistral:7b'].includes(this.settings.default_model)) {
        this.settings.default_model = 'qwen2.5:7b';
        await this.saveSetting('default_model', 'qwen2.5:7b');
      } else if (provider === 'openai' && this.settings.default_model.includes(':')) {
        this.settings.default_model = 'gpt-4o-mini';
        await this.saveSetting('default_model', 'gpt-4o-mini');
      }
      await this.saveSetting('llm_provider', provider);
      const names = { openai: 'OpenAI', azure: 'Azure OpenAI', ollama: 'Ollama (Local)' };
      this.$root.showToast('info', 'Provider changed', `Switched to ${names[provider] || provider}`);
    },

    // ── OpenAI ──────────────────────────────────────────────────

    async saveApiKey() {
      if (!this.settings.openai_api_key.trim()) return;
      this.savingKey = true;
      const resp = await fetch('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'openai_api_key', value: this.settings.openai_api_key, is_encrypted: true }),
      }).then(r => r.json());
      if (resp.success) this.$root.showToast('success', 'API Key Saved', 'Your OpenAI key has been saved securely');
      this.savingKey = false;
      this.$root.health.openai = true;
    },

    async validateApiKey() {
      this.validatingKey = true;
      this.keyValidationResult = null;
      const resp = await fetch('/api/validate/openai', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: this.settings.openai_api_key }),
      }).then(r => r.json());
      this.keyValidationResult = {
        success: resp.success,
        message: resp.success
          ? ('✓ Valid! Available models: ' + (resp.data?.available_models?.slice(0,5).join(', ') || ''))
          : (resp.error || 'Invalid key'),
      };
      this.validatingKey = false;
    },

    // ── Azure OpenAI ─────────────────────────────────────────────

    async saveAzureSettings() {
      const { azure_api_key, azure_endpoint, azure_deployment, azure_api_version } = this.settings;
      if (!azure_api_key.trim() || !azure_endpoint.trim() || !azure_deployment.trim()) {
        this.$root.showToast('error', 'Missing fields', 'API key, endpoint and deployment name are required');
        return;
      }
      this.savingKey = true;
      try {
        const saves = [
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'azure_api_key', value: azure_api_key, is_encrypted: true }) }),
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'azure_endpoint', value: azure_endpoint }) }),
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'azure_deployment', value: azure_deployment }) }),
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'azure_api_version', value: azure_api_version || '2024-10-21' }) }),
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'default_model', value: azure_deployment }) }),
        ];
        await Promise.all(saves);
        this.settings.default_model = azure_deployment;
        this.$root.showToast('success', 'Azure Settings Saved', 'Credentials stored securely');
        this.$root.health.openai = true;
      } catch (e) {
        this.$root.showToast('error', 'Save Failed', e.message);
      } finally {
        this.savingKey = false;
      }
    },

    async validateAzureKey() {
      const { azure_api_key, azure_endpoint, azure_deployment, azure_api_version } = this.settings;
      if (!azure_api_key || !azure_endpoint || !azure_deployment) {
        this.keyValidationResult = { success: false, message: 'Fill in endpoint, API key and deployment name first' };
        return;
      }
      this.validatingKey = true;
      this.keyValidationResult = null;
      const resp = await fetch('/api/validate/azure-openai', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: azure_api_key,
          azure_endpoint: azure_endpoint,
          deployment: azure_deployment,
          api_version: azure_api_version,
        }),
      }).then(r => r.json());
      this.keyValidationResult = {
        success: resp.success,
        message: resp.success
          ? ('✓ ' + (resp.data?.message || 'Azure OpenAI connection successful'))
          : (resp.error || 'Connection failed'),
      };
      this.validatingKey = false;
    },

    // ── Ollama ────────────────────────────────────────────────────

    async saveOllamaSettings() {
      const base_url = (this.settings.ollama_base_url || 'http://localhost:11434').trim();
      const model    = (this.settings.ollama_model    || 'qwen2.5:7b').trim();
      this.savingKey = true;
      try {
        await Promise.all([
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'ollama_base_url', value: base_url }) }),
          fetch('/api/settings', { method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: 'default_model', value: model }) }),
        ]);
        this.settings.ollama_base_url = base_url;
        this.settings.default_model   = model;
        this.$root.showToast('success', 'Ollama Settings Saved', `Using ${model} @ ${base_url}`);
        this.$root.health.openai = true;
      } catch (e) {
        this.$root.showToast('error', 'Save Failed', e.message);
      } finally {
        this.savingKey = false;
      }
    },

    async validateOllamaConnection() {
      this.validatingKey = true;
      this.keyValidationResult = null;
      const base_url = (this.settings.ollama_base_url || 'http://localhost:11434').trim();
      const model    = (this.settings.ollama_model    || 'qwen2.5:7b').trim();
      try {
        const resp = await fetch('/api/validate/ollama', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ base_url, model }),
        }).then(r => r.json());
        if (resp.success) {
          const installed = resp.data?.installed_models || [];
          const modelList = installed.length ? installed.slice(0, 8).join(', ') : 'none listed';
          this.keyValidationResult = {
            success: true,
            message: `✓ Ollama is running. Installed models: ${modelList}`,
          };
        } else {
          this.keyValidationResult = { success: false, message: resp.error || 'Could not connect to Ollama' };
        }
      } catch (e) {
        this.keyValidationResult = { success: false, message: `Connection error: ${e.message}` };
      } finally {
        this.validatingKey = false;
      }
    },

    // ── Shared ────────────────────────────────────────────────────

    async saveSetting(key, value) {
      await fetch('/api/settings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value: String(value) }),
      });
      if (key === 'theme') localStorage.setItem('plm_theme', value);
    },

    estimateCost(count, model) {
      // Ollama models are free/local
      if (model && model.includes(':')) return '0.0000 (local)';
      const costs = { 'gpt-4o': 0.005, 'gpt-4o-mini': 0.00015, 'gpt-3.5-turbo': 0.0005 };
      if (!(model in costs)) return 'N/A';
      const tokensPerFile = 1500;
      const total = count * tokensPerFile * costs[model] / 1000;
      return total.toFixed(4);
    },

    async loadAuditLog() {
      const resp = await fetch('/api/audit?limit=50').then(r => r.json());
      if (resp.success) this.auditEntries = resp.data.entries;
    },

    async exportSettings() {
      const resp = await fetch('/api/settings/export').then(r => r.json());
      if (resp.success) {
        const blob = new Blob([JSON.stringify(resp.data, null, 2)], { type: 'application/json' });
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'plm_settings.json'; a.click();
      }
    },

    async importSettings(event) {
      const file = event.target.files[0];
      if (!file) return;
      const text = await file.text();
      const settings = JSON.parse(text);
      for (const [key, value] of Object.entries(settings)) {
        await fetch('/api/settings', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value: String(value) }),
        });
      }
      await this.loadSettings();
      this.$root.showToast('success', 'Settings Imported', 'All settings have been imported');
    },

    formatDate(dt) {
      if (!dt) return '—';
      return new Date(dt).toLocaleString();
    },
  };
}
