// =========================================================
// Compass Desktop - Agentic Search Controller (v3.0)
// =========================================================

// --- UI Elements ---

// Sidebar: Stats & Horizon Folders
const statFilesCount = document.getElementById("stat-files-count");
const horizonCountBadge = document.getElementById("horizon-count-badge");
const horizonsListDiv = document.getElementById("horizons-list");
const btnPickAddFolder = document.getElementById("btn-pick-add-folder");
const folderValidationError = document.getElementById("folder-validation-error");

// Sidebar: Index Engine Panel
const indexStatusPill = document.getElementById("index-status-pill");
const indexProgressFill = document.getElementById("index-progress-fill");
const indexProgressText = document.getElementById("index-progress-text");
const btnTogglePause = document.getElementById("btn-toggle-pause");
const indexErrorText = document.getElementById("index-error-text");
const btnScan = document.getElementById("btn-scan");
const btnScanForce = document.getElementById("btn-scan-force");
const privacyStatusLabel = document.getElementById("privacy-status-label");
const appTitleText = document.getElementById("app-title-text");
const appBadgeText = document.getElementById("app-badge-text");

// Main Content: Banners & Panels
const demoModeBanner = document.getElementById("demo-mode-banner");
const btnSeedSimulatedHistory = document.getElementById("btn-seed-simulated-history");
const btnSwitchToNormal = document.getElementById("btn-switch-to-normal");
const indexBuildingBanner = document.getElementById("index-building-banner");
const demoTryThesePanel = document.getElementById("demo-try-these-panel");
const demoQueriesGrid = document.getElementById("demo-queries-grid");
const emptyFoldersCta = document.getElementById("empty-folders-cta");
const btnCtaAddFolder = document.getElementById("btn-cta-add-folder");

// Spotlight Search & Results
const searchInput = document.getElementById("search-input");
const suggestionsToggle = document.getElementById("suggestions-toggle");
const routerFeedbackPanel = document.getElementById("router-feedback-panel");
const resultsCountText = document.getElementById("results-count-text");
const routerStrategyBadge = document.getElementById("router-strategy-badge");
const routerLatencyValue = document.getElementById("router-latency-value");
const resultsList = document.getElementById("results-list");

// First-Run Onboarding Wizard Elements
const onboardingOverlay = document.getElementById("onboarding-overlay");
const onboardingStep1 = document.getElementById("onboarding-step-1");
const onboardingStep2 = document.getElementById("onboarding-step-2");
const onboardingStep3 = document.getElementById("onboarding-step-3");
const privacyDataDirPath = document.getElementById("privacy-data-dir-path");
const btnWizardNextToFolders = document.getElementById("btn-wizard-next-to-folders");
const btnWizardSkip = document.getElementById("btn-wizard-skip");
const btnWizardSkip2 = document.getElementById("btn-wizard-skip-2");
const btnWizardTryDemo = document.getElementById("btn-wizard-try-demo");
const wizardKnownFoldersList = document.getElementById("wizard-known-folders-list");
const btnWizardPickCustom = document.getElementById("btn-wizard-pick-custom");
const wizardValidationError = document.getElementById("wizard-validation-error");
const btnWizardStartIndexing = document.getElementById("btn-wizard-start-indexing");
const btnWizardBackToStep1 = document.getElementById("btn-wizard-back-to-step1");
const wizardProgressFill = document.getElementById("wizard-progress-fill");
const wizardProgressLabel = document.getElementById("wizard-progress-label");
const wizardProgressNumbers = document.getElementById("wizard-progress-numbers");
const wizardCurrentFile = document.getElementById("wizard-current-file");
const btnWizardFinishSearching = document.getElementById("btn-wizard-finish-searching");

// Confirmation Remove Modal
const confirmRemoveOverlay = document.getElementById("confirm-remove-overlay");
const confirmRemoveFolderPath = document.getElementById("confirm-remove-folder-path");
const btnConfirmRemoveCancel = document.getElementById("btn-confirm-remove-cancel");
const btnConfirmRemoveProceed = document.getElementById("btn-confirm-remove-proceed");

// State Variables
let currentRows = [];
let selectedRowIndex = -1;
let currentAppMode = "normal";
let currentDataDir = "";
let pendingRemovePath = null;
let indexPollTimer = null;
let isIndexingActive = false;
let wizardSelectedFolders = new Set();

// --- 1. Security & Auth Guard ---

function checkAuthResponse(response) {
    if (response && (response.status === 401 || response.status === 403)) {
        const overlay = document.getElementById("unauthorized-overlay");
        if (overlay) {
            overlay.classList.remove("hidden");
            const heading = overlay.querySelector("h2");
            const msg = overlay.querySelector("p");
            if (response.status === 401) {
                if (heading) heading.textContent = "Session Required";
                if (msg) msg.textContent = "Open Compass from the app window or tray icon.";
            } else {
                if (heading) heading.textContent = "Access Restricted";
                if (msg) msg.textContent = "This action is restricted in current mode.";
            }
        }
        return false;
    }
    return true;
}

// --- 2. Format Helpers ---

function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatRelativeTime(timestamp) {
    if (!timestamp) return "";
    const now = Math.floor(Date.now() / 1000);
    const diff = Math.max(0, now - timestamp);

    if (diff < 60) return "Just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 172800) return "Yesterday";
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function getFileBadge(fileType) {
    const ext = (fileType || "").toLowerCase();
    if (ext === ".pdf") {
        return `
            <div class="file-badge file-badge-pdf" title="PDF Document">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>`;
    }
    if (ext === ".docx" || ext === ".doc") {
        return `
            <div class="file-badge file-badge-docx" title="Word Document">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>
            </div>`;
    }
    if ([".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".json", ".yaml", ".yml"].includes(ext)) {
        return `
            <div class="file-badge file-badge-code" title="Code Source">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 18 22 12 16 6"></polyline><polyline points="8 6 2 12 8 18"></polyline></svg>
            </div>`;
    }
    return `
        <div class="file-badge file-badge-text" title="Document">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
        </div>`;
}

// --- 3. System Info & Mode Management ---

async function checkSystemInfo() {
    try {
        const response = await fetch("/api/system/info");
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            currentAppMode = data.mode || "normal";
            currentDataDir = data.data_dir || "";

            if (privacyDataDirPath) {
                privacyDataDirPath.textContent = currentDataDir;
            }

            if (currentAppMode === "demo") {
                document.title = "Compass (Demo) - Agentic Desktop Search";
                if (demoModeBanner) demoModeBanner.classList.remove("hidden");
                if (appBadgeText) appBadgeText.textContent = "Demo Mode";
                if (privacyStatusLabel) privacyStatusLabel.textContent = "Demo Profile";
                loadSuggestedQueries();
            } else {
                document.title = "Compass - Agentic Desktop Search";
                if (demoModeBanner) demoModeBanner.classList.add("hidden");
                if (demoTryThesePanel) demoTryThesePanel.classList.add("hidden");
                if (appBadgeText) appBadgeText.textContent = "Desktop Search";
                if (privacyStatusLabel) privacyStatusLabel.textContent = "Local & Private";
            }
        }
    } catch (e) {
        console.error("Failed to load system info:", e);
    }
}

async function switchMode(targetMode) {
    try {
        const response = await fetch("/api/system/mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: targetMode })
        });
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            // Process will restart, show brief transition feedback
            document.body.innerHTML = `
                <div style="height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#090a0d;color:#f1f3f5;font-family:sans-serif;">
                    <div class="mini-spinner" style="width:32px;height:32px;border:3px solid rgba(59,130,246,0.2);border-top-color:#3b82f6;border-radius:50%;animation:spin 1s linear infinite;margin-bottom:16px;"></div>
                    <h2>Switching to ${targetMode} mode...</h2>
                    <p style="color:#94a3b8;font-size:13px;margin-top:6px;">Restarting Compass background shell.</p>
                </div>
            `;
            setTimeout(() => window.location.reload(), 2500);
        }
    } catch (e) {
        alert("Failed to switch mode: " + e.message);
    }
}

async function loadSuggestedQueries() {
    try {
        const response = await fetch("/api/demo/suggested-queries");
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            const queries = data.suggested_queries || [];
            if (queries.length > 0 && demoTryThesePanel && demoQueriesGrid) {
                demoQueriesGrid.innerHTML = "";
                queries.forEach(q => {
                    const card = document.createElement("div");
                    card.className = "demo-query-card";
                    card.innerHTML = `
                        <div class="query-card-top">
                            <span class="query-card-text">"${q.query}"</span>
                            <span class="strategy-tag ${q.strategy}">${q.strategy}</span>
                        </div>
                        <div class="query-card-desc">${q.description}</div>
                    `;
                    card.addEventListener("click", () => {
                        searchInput.value = q.query;
                        executeSearch();
                    });
                    demoQueriesGrid.appendChild(card);
                });
                if (!searchInput.value.trim()) {
                    demoTryThesePanel.classList.remove("hidden");
                }
            }
        }
    } catch (e) {
        console.error("Failed to load suggested queries:", e);
    }
}

async function loadSimulatedHistory() {
    try {
        btnSeedSimulatedHistory.disabled = true;
        btnSeedSimulatedHistory.textContent = "Loading...";
        const response = await fetch("/api/demo/simulate-history", { method: "POST" });
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            btnSeedSimulatedHistory.textContent = "Simulated History Loaded";
            setTimeout(() => {
                btnSeedSimulatedHistory.disabled = false;
                btnSeedSimulatedHistory.textContent = "Load Simulated History";
            }, 3000);
            if (!searchInput.value.trim()) {
                loadRecommendations();
            }
        }
    } catch (e) {
        alert("Failed to load simulated history: " + e.message);
        btnSeedSimulatedHistory.disabled = false;
        btnSeedSimulatedHistory.textContent = "Load Simulated History";
    }
}

// --- 4. Monitored Folders Management ---

async function loadHorizons() {
    try {
        const response = await fetch("/api/monitored");
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            const horizons = data.monitored || [];
            
            if (horizonCountBadge) horizonCountBadge.textContent = horizons.length;
            
            horizonsListDiv.innerHTML = "";
            horizons.forEach(h => {
                const item = document.createElement("div");
                item.className = "horizon-item";
                const isWatching = h.watching !== false;
                item.innerHTML = `
                    <div class="horizon-details" title="${h.path}">
                        <svg class="horizon-folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <div class="horizon-text">
                            <span class="horizon-name">${h.label || h.path}</span>
                            <div style="display:flex;align-items:center;gap:8px;">
                                <span class="horizon-files">${h.file_count || 0} files</span>
                                <span class="watching-badge" title="${isWatching ? 'Active directory watcher' : 'Observer idle'}">
                                    <span class="watching-dot" style="background:${isWatching ? '#10b981' : '#64748b'}"></span>
                                    <span>${isWatching ? 'Watching' : 'Idle'}</span>
                                </span>
                            </div>
                        </div>
                    </div>
                    <button class="horizon-del-btn" title="Remove folder">&times;</button>
                `;
                
                item.querySelector(".horizon-del-btn").addEventListener("click", (e) => {
                    e.stopPropagation();
                    openConfirmRemoveModal(h.path);
                });
                
                horizonsListDiv.appendChild(item);
            });

            // If in normal mode with 0 monitored folders, trigger first-run wizard
            if (horizons.length === 0) {
                if (emptyFoldersCta && !searchInput.value.trim()) {
                    emptyFoldersCta.classList.remove("hidden");
                }
                const hasSkipped = localStorage.getItem("compass_onboarding_skipped") === "true";
                if (currentAppMode === "normal" && !hasSkipped) {
                    showOnboardingWizard();
                }
            } else {
                if (emptyFoldersCta) emptyFoldersCta.classList.add("hidden");
            }
        }
    } catch (e) {
        console.error("Failed to load monitored folders:", e);
    }
}

async function pickAndAddFolder() {
    folderValidationError.classList.add("hidden");
    try {
        const pickRes = await fetch("/api/system/pick-folder", { method: "POST" });
        if (!checkAuthResponse(pickRes)) return;
        const pickData = await pickRes.json();
        const chosen = pickData.chosen_path;
        if (!chosen) return;

        const addRes = await fetch("/api/monitored", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: chosen })
        });
        if (!checkAuthResponse(addRes)) return;
        if (addRes.ok) {
            folderValidationError.classList.add("hidden");
            await loadHorizons();
            await pollIndexStatus();
        } else {
            const err = await addRes.json();
            folderValidationError.textContent = err.detail || "Invalid folder selection";
            folderValidationError.classList.remove("hidden");
        }
    } catch (e) {
        folderValidationError.textContent = e.message;
        folderValidationError.classList.remove("hidden");
    }
}

function openConfirmRemoveModal(path) {
    pendingRemovePath = path;
    if (confirmRemoveFolderPath) confirmRemoveFolderPath.textContent = path;
    if (confirmRemoveOverlay) confirmRemoveOverlay.classList.remove("hidden");
}

function closeConfirmRemoveModal() {
    pendingRemovePath = null;
    if (confirmRemoveOverlay) confirmRemoveOverlay.classList.add("hidden");
}

async function executeRemoveFolder() {
    if (!pendingRemovePath) return;
    const path = pendingRemovePath;
    closeConfirmRemoveModal();

    try {
        const response = await fetch(`/api/monitored?path=${encodeURIComponent(path)}`, {
            method: "DELETE"
        });
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            await loadHorizons();
            await pollIndexStatus();
            if (!searchInput.value.trim()) loadRecommendations();
        }
    } catch (e) {
        console.error("Failed to remove monitored folder:", e);
    }
}

// --- 5. Index Engine Status & Lifecycle ---

async function pollIndexStatus() {
    try {
        const response = await fetch("/api/index/status");
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            const state = data.state || "idle";
            const processed = data.processed || 0;
            const total = data.total_expected || 0;
            const isPaused = state === "paused";

            isIndexingActive = (state === "indexing" || state === "reconciling");

            // Update status pill
            if (indexStatusPill) {
                if (state === "idle") {
                    indexStatusPill.textContent = "Up to date";
                    indexStatusPill.style.background = "rgba(16, 185, 129, 0.1)";
                    indexStatusPill.style.color = "#34d399";
                    indexStatusPill.style.borderColor = "rgba(16, 185, 129, 0.25)";
                } else if (state === "indexing") {
                    indexStatusPill.textContent = "Indexing";
                    indexStatusPill.style.background = "rgba(59, 130, 246, 0.1)";
                    indexStatusPill.style.color = "#60a5fa";
                    indexStatusPill.style.borderColor = "rgba(59, 130, 246, 0.25)";
                } else if (state === "reconciling") {
                    indexStatusPill.textContent = "Reconciling";
                    indexStatusPill.style.background = "rgba(139, 92, 246, 0.1)";
                    indexStatusPill.style.color = "#c084fc";
                    indexStatusPill.style.borderColor = "rgba(139, 92, 246, 0.25)";
                } else if (state === "paused") {
                    indexStatusPill.textContent = "Paused";
                    indexStatusPill.style.background = "rgba(245, 158, 11, 0.1)";
                    indexStatusPill.style.color = "#fbbf24";
                    indexStatusPill.style.borderColor = "rgba(245, 158, 11, 0.25)";
                } else if (state === "error") {
                    indexStatusPill.textContent = "Error";
                    indexStatusPill.style.background = "rgba(244, 63, 94, 0.1)";
                    indexStatusPill.style.color = "#fda4af";
                    indexStatusPill.style.borderColor = "rgba(244, 63, 94, 0.25)";
                }
            }

            // Update Progress Bar
            if (indexProgressFill && indexProgressText) {
                if (isIndexingActive && total > 0) {
                    const pct = Math.min(100, Math.round((processed / total) * 100));
                    indexProgressFill.style.width = `${pct}%`;
                    indexProgressText.textContent = `${state === "reconciling" ? "Reconciling" : "Indexing"} ${processed} of ${total}`;
                } else if (isPaused) {
                    indexProgressText.textContent = "Indexing paused";
                } else {
                    indexProgressFill.style.width = "100%";
                    indexProgressText.textContent = "All folders up to date";
                }
            }

            // Update Pause/Resume button
            if (btnTogglePause) {
                btnTogglePause.textContent = isPaused ? "Resume" : "Pause";
            }

            // Update Error Banner
            if (indexErrorText) {
                if (state === "error" && data.last_error) {
                    indexErrorText.textContent = data.last_error;
                    indexErrorText.classList.remove("hidden");
                } else {
                    indexErrorText.classList.add("hidden");
                }
            }

            // Update Incomplete Warning Banner in Search view
            if (indexBuildingBanner) {
                if (isIndexingActive) {
                    indexBuildingBanner.classList.remove("hidden");
                } else {
                    indexBuildingBanner.classList.add("hidden");
                }
            }

            // Update files count metric
            if (statFilesCount) {
                const totalFiles = (data.roots || []).reduce((acc, r) => acc + (r.file_count || 0), 0);
                statFilesCount.textContent = totalFiles;
            }

            // Update wizard progress if step 3 is visible
            if (onboardingOverlay && !onboardingOverlay.classList.contains("hidden") && !onboardingStep3.classList.contains("hidden")) {
                if (wizardProgressFill && wizardProgressLabel && wizardProgressNumbers) {
                    if (total > 0) {
                        const pct = Math.min(100, Math.round((processed / total) * 100));
                        wizardProgressFill.style.width = `${pct}%`;
                        wizardProgressLabel.textContent = isIndexingActive ? "Indexing files..." : "Initial index complete";
                        wizardProgressNumbers.textContent = `${processed} / ${total}`;
                        if (wizardCurrentFile && data.current_file) {
                            wizardCurrentFile.textContent = data.current_file;
                        }
                    }
                }
            }
        }
    } catch (e) {
        console.error("Index status poll error:", e);
    } finally {
        // Schedule next poll: 1.5s while indexing, 10s when idle
        clearTimeout(indexPollTimer);
        const nextInterval = isIndexingActive ? 1500 : 10000;
        indexPollTimer = setTimeout(pollIndexStatus, nextInterval);
    }
}

async function togglePauseResume() {
    try {
        const isPaused = btnTogglePause.textContent === "Resume";
        const endpoint = isPaused ? "/api/index/resume" : "/api/index/pause";
        const response = await fetch(endpoint, { method: "POST" });
        if (!checkAuthResponse(response)) return;
        await pollIndexStatus();
    } catch (e) {
        console.error("Error toggling pause/resume:", e);
    }
}

async function triggerRescan(force = false) {
    try {
        const response = await fetch("/api/index/rescan", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ force })
        });
        if (!checkAuthResponse(response)) return;
        await pollIndexStatus();
    } catch (e) {
        console.error("Error triggering rescan:", e);
    }
}

// --- 6. First-Run Onboarding Wizard ---

function showOnboardingWizard() {
    if (!onboardingOverlay) return;
    onboardingOverlay.classList.remove("hidden");
    onboardingStep1.classList.remove("hidden");
    onboardingStep2.classList.add("hidden");
    onboardingStep3.classList.add("hidden");
}

function hideOnboardingWizard(rememberSkip = true) {
    if (rememberSkip) {
        localStorage.setItem("compass_onboarding_skipped", "true");
    }
    if (onboardingOverlay) onboardingOverlay.classList.add("hidden");
}

async function proceedToWizardStep2() {
    onboardingStep1.classList.add("hidden");
    onboardingStep2.classList.remove("hidden");
    wizardKnownFoldersList.innerHTML = `<div style="color:#94a3b8;font-size:12px;padding:10px;">Detecting known folders...</div>`;

    try {
        const response = await fetch("/api/system/known-folders");
        if (!checkAuthResponse(response)) return;
        const data = await response.json();
        const folders = data.folders || {};

        wizardKnownFoldersList.innerHTML = "";
        wizardSelectedFolders.clear();

        for (const [name, path] of Object.entries(folders)) {
            const row = document.createElement("div");
            row.className = "folder-checkbox-row";
            row.innerHTML = `
                <label class="folder-checkbox-label">
                    <input type="checkbox" data-path="${path}" checked>
                    <span>${name}</span>
                </label>
                <span class="folder-estimate-badge" id="est-${name}">Calculating...</span>
            `;
            wizardKnownFoldersList.appendChild(row);
            wizardSelectedFolders.add(path);

            const chk = row.querySelector("input");
            chk.addEventListener("change", () => {
                if (chk.checked) wizardSelectedFolders.add(path);
                else wizardSelectedFolders.delete(path);
            });

            // Asynchronously fetch file estimate
            fetch("/api/monitored/estimate", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path })
            }).then(r => r.json()).then(est => {
                const el = document.getElementById(`est-${name}`);
                if (el) {
                    el.textContent = `~${est.supported_files || 0} files${est.capped ? '+' : ''}`;
                }
            }).catch(() => {
                const el = document.getElementById(`est-${name}`);
                if (el) el.textContent = "";
            });
        }
    } catch (e) {
        wizardKnownFoldersList.innerHTML = `<div style="color:#fda4af;font-size:12px;">Could not detect known folders: ${e.message}</div>`;
    }
}

async function pickWizardCustomFolder() {
    wizardValidationError.classList.add("hidden");
    try {
        const pickRes = await fetch("/api/system/pick-folder", { method: "POST" });
        if (!checkAuthResponse(pickRes)) return;
        const pickData = await pickRes.json();
        const chosen = pickData.chosen_path;
        if (!chosen) return;

        // Estimate files
        const estRes = await fetch("/api/monitored/estimate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: chosen })
        });
        const est = await estRes.json();

        const row = document.createElement("div");
        row.className = "folder-checkbox-row";
        row.innerHTML = `
            <label class="folder-checkbox-label">
                <input type="checkbox" data-path="${chosen}" checked>
                <span>${chosen}</span>
            </label>
            <span class="folder-estimate-badge">~${est.supported_files || 0} files</span>
        `;
        wizardKnownFoldersList.appendChild(row);
        wizardSelectedFolders.add(chosen);

        const chk = row.querySelector("input");
        chk.addEventListener("change", () => {
            if (chk.checked) wizardSelectedFolders.add(chosen);
            else wizardSelectedFolders.delete(chosen);
        });
    } catch (e) {
        wizardValidationError.textContent = e.message;
        wizardValidationError.classList.remove("hidden");
    }
}

async function startWizardIndexing() {
    if (wizardSelectedFolders.size === 0) {
        wizardValidationError.textContent = "Please select at least one folder or click 'Skip for now'.";
        wizardValidationError.classList.remove("hidden");
        return;
    }

    onboardingStep2.classList.add("hidden");
    onboardingStep3.classList.remove("hidden");

    // Add all selected folders
    for (const path of wizardSelectedFolders) {
        try {
            await fetch("/api/monitored", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ path })
            });
        } catch (e) {
            console.error("Error adding folder during wizard:", e);
        }
    }

    await loadHorizons();
    await pollIndexStatus();
}

// --- 7. Search Execution & Ranking Feedback ---

async function executeSearch() {
    const query = searchInput.value.trim();

    if (!query) {
        routerFeedbackPanel.classList.add("hidden");
        if (currentAppMode === "demo" && demoTryThesePanel) {
            demoTryThesePanel.classList.remove("hidden");
        }
        loadRecommendations();
        return;
    }

    if (demoTryThesePanel) demoTryThesePanel.classList.add("hidden");
    if (emptyFoldersCta) emptyFoldersCta.classList.add("hidden");

    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&limit=12`);
        if (!checkAuthResponse(response)) return;
        
        if (response.ok) {
            const data = await response.json();
            const results = data.results || [];
            
            // Update Router Feedback Bar
            routerFeedbackPanel.classList.remove("hidden");
            resultsCountText.textContent = `${results.length} result${results.length === 1 ? '' : 's'}`;
            
            const strategy = data.strategy || "hybrid";
            routerStrategyBadge.textContent = strategy.toUpperCase();
            routerStrategyBadge.className = `strategy-badge strategy-${strategy}`;
            
            routerLatencyValue.textContent = `${(data.latency_ms || 0).toFixed(1)} ms`;

            // Render Results List
            resultsList.innerHTML = "";
            currentRows = [];
            selectedRowIndex = -1;

            if (results.length === 0) {
                resultsList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                            </svg>
                        </div>
                        <p class="empty-text">No documents matching "${query}"</p>
                        <p class="empty-subtext">Check your spelling or try broader concept keywords.</p>
                    </div>
                `;
                return;
            }

            results.forEach((r, idx) => {
                const row = document.createElement("div");
                row.className = "result-row";
                row.dataset.index = idx;
                row.dataset.filepath = r.filepath;

                const badge = getFileBadge(r.file_type);
                const sizeStr = formatBytes(r.file_size);
                const timeStr = formatRelativeTime(r.modified_at);

                row.innerHTML = `
                    ${badge}
                    <div class="file-info">
                        <div class="file-name-row">
                            <span class="file-name">${r.filename}</span>
                            <div class="match-meta">
                                ${r.score !== undefined ? `<span class="score-badge">${(r.score).toFixed(2)}</span>` : ""}
                                <span class="file-size">${sizeStr}</span>
                                <span class="file-time">${timeStr}</span>
                            </div>
                        </div>
                        <div class="file-path">${r.filepath}</div>
                        ${r.snippet ? `<div class="file-snippet">${r.snippet}</div>` : ""}
                    </div>
                `;

                row.addEventListener("click", () => {
                    selectRow(idx);
                    logFileAccessAndLaunch(r.filepath);
                });

                resultsList.appendChild(row);
                currentRows.push(row);
            });

            if (currentRows.length > 0) {
                selectRow(0);
            }
        }
    } catch (e) {
        console.error("Search request failed:", e);
    }
}

// --- 8. Zero-Query Recommendations ---

async function loadRecommendations() {
    if (searchInput.value.trim()) return;

    if (!suggestionsToggle || !suggestionsToggle.checked) {
        resultsList.innerHTML = "";
        currentRows = [];
        return;
    }

    try {
        const response = await fetch("/api/recommendations?limit=6");
        if (!checkAuthResponse(response)) return;
        if (response.ok) {
            const data = await response.json();
            const recs = data.recommendations || [];

            resultsList.innerHTML = "";
            currentRows = [];

            if (recs.length === 0) return;

            const sectionHeader = document.createElement("div");
            sectionHeader.className = "section-header-row";
            sectionHeader.innerHTML = `<span>Recent & Suggested Files</span>`;
            resultsList.appendChild(sectionHeader);

            recs.forEach((r, idx) => {
                const row = document.createElement("div");
                row.className = "result-row";
                row.dataset.index = idx;
                row.dataset.filepath = r.filepath;

                const badge = getFileBadge(r.file_type);
                const sizeStr = formatBytes(r.file_size);
                const timeStr = formatRelativeTime(r.modified_at);

                row.innerHTML = `
                    ${badge}
                    <div class="file-info">
                        <div class="file-name-row">
                            <span class="file-name">${r.filename}</span>
                            <div class="match-meta">
                                <span class="file-size">${sizeStr}</span>
                                <span class="file-time">${timeStr}</span>
                            </div>
                        </div>
                        <div class="file-path">${r.filepath}</div>
                    </div>
                `;

                row.addEventListener("click", () => {
                    selectRow(idx);
                    logFileAccessAndLaunch(r.filepath);
                });

                resultsList.appendChild(row);
                currentRows.push(row);
            });

            if (currentRows.length > 0) {
                selectRow(0);
            }
        }
    } catch (e) {
        console.error("Failed to load recommendations:", e);
    }
}

async function logFileAccessAndLaunch(filepath) {
    try {
        await fetch("/api/open", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filepath })
        });
    } catch (e) {
        console.error("Launch error:", e);
    }
}

// --- 9. Keyboard Navigation ---

function selectRow(index) {
    if (index < 0 || index >= currentRows.length) return;
    currentRows.forEach((r, i) => {
        if (i === index) {
            r.classList.add("is-selected");
            r.scrollIntoView({ block: "nearest", behavior: "smooth" });
        } else {
            r.classList.remove("is-selected");
        }
    });
    selectedRowIndex = index;
}

window.addEventListener("keydown", (e) => {
    if (currentRows.length === 0) return;

    if (e.key === "ArrowDown") {
        e.preventDefault();
        const nextIndex = selectedRowIndex < currentRows.length - 1 ? selectedRowIndex + 1 : 0;
        selectRow(nextIndex);
    } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prevIndex = selectedRowIndex > 0 ? selectedRowIndex - 1 : currentRows.length - 1;
        selectRow(prevIndex);
    } else if (e.key === "Enter") {
        if (selectedRowIndex >= 0 && selectedRowIndex < currentRows.length) {
            e.preventDefault();
            const selectedRow = currentRows[selectedRowIndex];
            const path = selectedRow.dataset.filepath;
            if (path) logFileAccessAndLaunch(path);
        }
    } else if (e.key === "Escape") {
        if (searchInput.value) {
            e.preventDefault();
            searchInput.value = "";
            executeSearch();
        }
    }
});

// --- 10. Initialization & Listeners ---

let searchDebounceTimer;
searchInput.addEventListener("input", () => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(executeSearch, 200);
});

if (suggestionsToggle) {
    suggestionsToggle.addEventListener("change", () => {
        localStorage.setItem("compass_show_suggestions", suggestionsToggle.checked ? "true" : "false");
        if (!searchInput.value.trim()) loadRecommendations();
    });
}

// Sidebar Buttons
if (btnPickAddFolder) btnPickAddFolder.addEventListener("click", pickAndAddFolder);
if (btnScan) btnScan.addEventListener("click", () => triggerRescan(false));
if (btnScanForce) btnScanForce.addEventListener("click", () => triggerRescan(true));
if (btnTogglePause) btnTogglePause.addEventListener("click", togglePauseResume);
if (btnCtaAddFolder) btnCtaAddFolder.addEventListener("click", pickAndAddFolder);

// Demo Mode Banner Buttons
if (btnSeedSimulatedHistory) btnSeedSimulatedHistory.addEventListener("click", loadSimulatedHistory);
if (btnSwitchToNormal) btnSwitchToNormal.addEventListener("click", () => switchMode("normal"));

// Wizard Buttons
if (btnWizardNextToFolders) btnWizardNextToFolders.addEventListener("click", proceedToWizardStep2);
if (btnWizardSkip) btnWizardSkip.addEventListener("click", () => hideOnboardingWizard(true));
if (btnWizardSkip2) btnWizardSkip2.addEventListener("click", () => hideOnboardingWizard(true));
if (btnWizardTryDemo) btnWizardTryDemo.addEventListener("click", () => switchMode("demo"));
if (btnWizardPickCustom) btnWizardPickCustom.addEventListener("click", pickWizardCustomFolder);
if (btnWizardStartIndexing) btnWizardStartIndexing.addEventListener("click", startWizardIndexing);
if (btnWizardBackToStep1) btnWizardBackToStep1.addEventListener("click", () => {
    onboardingStep2.classList.add("hidden");
    onboardingStep1.classList.remove("hidden");
});
if (btnWizardFinishSearching) btnWizardFinishSearching.addEventListener("click", () => {
    hideOnboardingWizard(false);
    searchInput.focus();
});

// Confirm Modal Buttons
if (btnConfirmRemoveCancel) btnConfirmRemoveCancel.addEventListener("click", closeConfirmRemoveModal);
if (btnConfirmRemoveProceed) btnConfirmRemoveProceed.addEventListener("click", executeRemoveFolder);

// Page Load
window.addEventListener("DOMContentLoaded", async () => {
    await checkSystemInfo();
    await loadHorizons();
    await pollIndexStatus();

    const savedSuggestions = localStorage.getItem("compass_show_suggestions");
    if (suggestionsToggle) {
        suggestionsToggle.checked = savedSuggestions === "true";
    }

    if (!searchInput.value.trim()) {
        loadRecommendations();
    }
});
