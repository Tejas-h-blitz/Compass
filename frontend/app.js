// =========================================================
// Compass Desktop - Agentic Search Controller
// =========================================================

// UI Elements
const statFilesCount = document.getElementById("stat-files-count");
const horizonCountBadge = document.getElementById("horizon-count-badge");
const horizonsListDiv = document.getElementById("horizons-list");
const scanPathInput = document.getElementById("scan-path-input");
const btnAddHorizon = document.getElementById("btn-add-horizon");
const btnScan = document.getElementById("btn-scan");
const btnScanForce = document.getElementById("btn-scan-force");
const scanStatusDiv = document.getElementById("scan-status");
const scanStatusText = document.getElementById("scan-status-text");
const scanResultDiv = document.getElementById("scan-result");
const scanResultDetails = document.getElementById("scan-result-details");
const indexStatusPill = document.getElementById("index-status-pill");

const searchInput = document.getElementById("search-input");
const suggestionsToggle = document.getElementById("suggestions-toggle");

const routerFeedbackPanel = document.getElementById("router-feedback-panel");
const resultsCountText = document.getElementById("results-count-text");
const routerStrategyBadge = document.getElementById("router-strategy-badge");
const routerLatencyValue = document.getElementById("router-latency-value");
const resultsList = document.getElementById("results-list");

// Keyboard Navigation State
let currentRows = [];
let selectedRowIndex = -1;

// 1. Format Helpers
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
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
            </div>
        `;
    }
    if (ext === ".docx" || ext === ".doc") {
        return `
            <div class="file-badge file-badge-docx" title="Word Document">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                </svg>
            </div>
        `;
    }
    if ([".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".json", ".yaml", ".yml"].includes(ext)) {
        return `
            <div class="file-badge file-badge-code" title="Code Source">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="16 18 22 12 16 6"></polyline>
                    <polyline points="8 6 2 12 8 18"></polyline>
                </svg>
            </div>
        `;
    }
    if (ext === ".txt" || ext === ".md") {
        return `
            <div class="file-badge file-badge-text" title="Text Note">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                    <polyline points="14 2 14 8 20 8"></polyline>
                    <line x1="16" y1="13" x2="8" y2="13"></line>
                    <line x1="16" y1="17" x2="8" y2="17"></line>
                    <line x1="10" y1="9" x2="8" y2="9"></line>
                </svg>
            </div>
        `;
    }
    return `
        <div class="file-badge file-badge-generic" title="File">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path>
                <polyline points="13 2 13 9 20 9"></polyline>
            </svg>
        </div>
    `;
}

// 2. Dashboard Stats & Horizon Management
async function updateDashboardStats() {
    try {
        const response = await fetch("/api/stats");
        if (response.ok) {
            const data = await response.json();
            if (statFilesCount) statFilesCount.textContent = data.total_files || 0;
        }
    } catch (e) {
        console.error("Failed to load statistics:", e);
    }
}

async function loadHorizons() {
    try {
        const response = await fetch("/api/horizons");
        if (response.ok) {
            const data = await response.json();
            const horizons = data.horizons || [];
            
            if (horizonCountBadge) horizonCountBadge.textContent = horizons.length;
            
            if (horizons.length === 0) {
                horizonsListDiv.innerHTML = `<span style="font-size: 11px; color: var(--text-muted); font-style: italic; padding: 4px 6px;">No folders indexed yet.</span>`;
                return;
            }

            horizonsListDiv.innerHTML = "";
            horizons.forEach(h => {
                const item = document.createElement("div");
                item.className = "horizon-item";
                item.innerHTML = `
                    <div class="horizon-details" title="${h.path}">
                        <svg class="horizon-folder-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        </svg>
                        <div class="horizon-text">
                            <span class="horizon-name">${h.label || h.path}</span>
                            <span class="horizon-files">${h.file_count} files</span>
                        </div>
                    </div>
                    <button class="horizon-del-btn" title="Remove folder">&times;</button>
                `;
                
                item.querySelector(".horizon-del-btn").addEventListener("click", (e) => {
                    e.stopPropagation();
                    removeHorizon(h.path);
                });
                
                horizonsListDiv.appendChild(item);
            });
        }
    } catch (e) {
        console.error("Failed to load horizons:", e);
    }
}

async function addHorizon() {
    const path = scanPathInput.value.trim();
    if (!path) return;
    
    scanStatusDiv.classList.remove("hidden");
    scanStatusText.textContent = "Scanning directory...";
    if (btnAddHorizon) btnAddHorizon.disabled = true;
    btnScan.disabled = true;

    try {
        const response = await fetch("/api/horizons", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ path: path })
        });
        
        if (response.ok) {
            const data = await response.json();
            scanPathInput.value = "";
            scanResultDetails.textContent = `Indexed ${data.stats.scanned} files (${data.stats.updated} updated)`;
            scanResultDiv.classList.remove("hidden");
            setTimeout(() => scanResultDiv.classList.add("hidden"), 4000);
            
            await loadHorizons();
            await updateDashboardStats();
            if (!searchInput.value.trim()) loadRecommendations();
        } else {
            const err = await response.json();
            alert(`Failed: ${err.detail || "Error adding folder"}`);
        }
    } catch (e) {
        alert(`Request error: ${e.message}`);
    } finally {
        scanStatusDiv.classList.add("hidden");
        if (btnAddHorizon) btnAddHorizon.disabled = false;
        btnScan.disabled = false;
    }
}

async function removeHorizon(path) {
    if (!confirm(`Remove "${path}" from search horizons?`)) return;
    try {
        const response = await fetch(`/api/horizons?path=${encodeURIComponent(path)}`, {
            method: "DELETE"
        });
        if (response.ok) {
            loadHorizons();
            updateDashboardStats();
            if (!searchInput.value.trim()) loadRecommendations();
        }
    } catch (e) {
        console.error("Failed to remove horizon:", e);
    }
}

// 3. Trigger Scanning
async function triggerScan(force = false) {
    const path = scanPathInput.value.trim();

    scanStatusDiv.classList.remove("hidden");
    scanStatusText.textContent = force ? "Re-indexing all horizons..." : "Scanning for updates...";
    scanResultDiv.classList.add("hidden");
    if (indexStatusPill) {
        indexStatusPill.textContent = "Syncing...";
        indexStatusPill.style.background = "rgba(59, 130, 246, 0.1)";
        indexStatusPill.style.color = "#60a5fa";
        indexStatusPill.style.borderColor = "rgba(59, 130, 246, 0.25)";
    }
    btnScan.disabled = true;
    btnScanForce.disabled = true;

    try {
        let response;
        if (path) {
            response = await fetch("/api/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ directory_path: path, force: force })
            });
        } else {
            response = await fetch(`/api/scan-all?force=${force}`, {
                method: "POST"
            });
        }

        if (response.ok) {
            const data = await response.json();
            const stats = data.stats;
            scanResultDetails.textContent = `Scanned ${stats.scanned} files · ${stats.updated} indexed`;
            scanResultDiv.classList.remove("hidden");
            setTimeout(() => scanResultDiv.classList.add("hidden"), 4000);
            loadHorizons();
            loadRecommendations();
        } else {
            const err = await response.json();
            alert(`Scan error: ${err.detail || "Unknown error"}`);
        }
    } catch (e) {
        alert(`Scan error: ${e.message}`);
    } finally {
        scanStatusDiv.classList.add("hidden");
        if (indexStatusPill) {
            indexStatusPill.textContent = "Ready";
            indexStatusPill.style.background = "";
            indexStatusPill.style.color = "";
            indexStatusPill.style.borderColor = "";
        }
        btnScan.disabled = false;
        btnScanForce.disabled = false;
        updateDashboardStats();
    }
}

// 4. Clean Empty State Placeholder
function renderEmptyState() {
    routerFeedbackPanel.classList.add("hidden");
    currentRows = [];
    selectedRowIndex = -1;
    resultsList.innerHTML = `
        <div class="empty-state">
            <div class="empty-icon">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="11" cy="11" r="8"></circle>
                    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                </svg>
            </div>
            <div class="empty-title">Ready to Search</div>
            <div class="empty-subtitle">Type a filename, code symbol, or concept to instantly find files across your monitored horizons.</div>
        </div>
    `;
}

// 5. Smart Recommendations (Zero-Query State)
async function loadRecommendations() {
    // If Suggestions toggle is OFF, keep screen distraction-free
    if (!suggestionsToggle || !suggestionsToggle.checked) {
        renderEmptyState();
        return;
    }

    try {
        const response = await fetch("/api/recommendations?limit=4");
        if (response.ok) {
            const data = await response.json();
            const recs = data.recommendations || [];
            
            if (recs.length === 0) {
                renderEmptyState();
                return;
            }

            routerFeedbackPanel.classList.add("hidden");
            resultsList.innerHTML = "";
            currentRows = [];
            selectedRowIndex = -1;

            // Clean Section Header
            const header = document.createElement("div");
            header.className = "list-section-header";
            header.innerHTML = `
                <span class="list-section-title">Suggested Files</span>
                <span class="list-section-meta">${recs.length} suggestions</span>
            `;
            resultsList.appendChild(header);

            recs.forEach((r, idx) => {
                const row = document.createElement("div");
                row.className = "item-row";
                row.dataset.filepath = r.filepath;
                row.dataset.index = idx;
                
                const iconBadge = getFileBadge(r.file_type);
                const sizeText = formatBytes(r.file_size);
                const relTime = formatRelativeTime(r.modified_at);

                // Clean human-friendly badge
                let tagClass = "tag-recent";
                let tagText = "Recent";
                if (r.badge === "FAVORITE" || r.badge === "FREQUENT") {
                    tagClass = "tag-frequent";
                    tagText = "Frequent";
                } else if (r.badge === "ACTIVE") {
                    tagClass = "tag-active";
                    tagText = "Active";
                }

                // Shorten directory path
                const pathParts = (r.filepath || "").replace(/\\/g, "/").split("/");
                const dirBreadcrumb = pathParts.length > 2 
                    ? pathParts.slice(-3, -1).join(" / ") 
                    : pathParts.slice(0, -1).join(" / ");

                row.innerHTML = `
                    <div class="row-main">
                        <div class="row-left">
                            ${iconBadge}
                            <div class="row-info">
                                <span class="row-filename">${r.filename}</span>
                                <span class="row-breadcrumb">${dirBreadcrumb || r.filepath}</span>
                            </div>
                        </div>
                        <div class="row-right">
                            <span class="context-tag ${tagClass}">${tagText}</span>
                            <span class="row-meta-sub">${sizeText}</span>
                        </div>
                    </div>
                    ${r.content_preview ? `<div class="row-snippet">${r.content_preview}</div>` : ""}
                `;

                row.addEventListener("click", () => {
                    selectRow(idx);
                    logFileAccessAndLaunch(r.filepath);
                });

                resultsList.appendChild(row);
                currentRows.push(row);
            });

            // Default selection to first item
            if (currentRows.length > 0) {
                selectRow(0);
            }
        }
    } catch (e) {
        console.error("Failed to load recommendations:", e);
    }
}

// 6. Log User Access & Launch File Locally
async function logFileAccessAndLaunch(filepath) {
    try {
        const response = await fetch("/api/log-access", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filepath: filepath })
        });
        
        if (response.ok) {
            updateDashboardStats();
            if (!searchInput.value.trim()) {
                loadRecommendations();
            }
        }
    } catch (e) {
        console.error("Failed to log file access:", e);
    }
}

// 7. Execute Search Query Routing
async function executeSearch() {
    const query = searchInput.value.trim();
    const personalize = true; // Always active in background

    if (!query) {
        loadRecommendations();
        return;
    }

    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&personalize=${personalize}`);
        if (response.ok) {
            const data = await response.json();
            const results = data.results || [];
            
            // Render Status Bar
            routerFeedbackPanel.classList.remove("hidden");
            resultsCountText.textContent = `${results.length} ${results.length === 1 ? "file" : "files"} found`;
            
            const strategy = data.strategy_chosen || "keyword";
            routerStrategyBadge.className = "strategy-badge";
            if (strategy === "keyword") {
                routerStrategyBadge.classList.add("badge-instant");
                routerStrategyBadge.textContent = "Instant";
            } else if (strategy === "semantic") {
                routerStrategyBadge.classList.add("badge-semantic");
                routerStrategyBadge.textContent = "Semantic";
            } else {
                routerStrategyBadge.classList.add("badge-hybrid");
                routerStrategyBadge.textContent = "Hybrid";
            }
            
            routerLatencyValue.textContent = `${data.latency_ms.toFixed(1)} ms`;

            // Render Results
            resultsList.innerHTML = "";
            currentRows = [];
            selectedRowIndex = -1;

            if (results.length === 0) {
                resultsList.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">
                            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="11" cy="11" r="8"></circle>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                                <line x1="8" y1="11" x2="14" y2="11"></line>
                            </svg>
                        </div>
                        <div class="empty-title">No matching files</div>
                        <div class="empty-subtitle">Try adjusting your search terms or verify that your target folder is added to Monitored Folders.</div>
                    </div>
                `;
                return;
            }

            results.forEach((r, idx) => {
                const row = document.createElement("div");
                row.className = "item-row";
                row.dataset.filepath = r.filepath;
                row.dataset.index = idx;
                
                const iconBadge = getFileBadge(r.file_type);
                const sizeText = formatBytes(r.file_size);
                const relTime = formatRelativeTime(r.modified_at);

                // Shorten directory path
                const pathParts = (r.filepath || "").replace(/\\/g, "/").split("/");
                const dirBreadcrumb = pathParts.length > 2 
                    ? pathParts.slice(-3, -1).join(" / ") 
                    : pathParts.slice(0, -1).join(" / ");

                row.innerHTML = `
                    <div class="row-main">
                        <div class="row-left">
                            ${iconBadge}
                            <div class="row-info">
                                <span class="row-filename">${r.filename}</span>
                                <span class="row-breadcrumb">${dirBreadcrumb || r.filepath}</span>
                            </div>
                        </div>
                        <div class="row-right">
                            <span class="row-meta-sub">${relTime}</span>
                            <span class="row-meta-sub">${sizeText}</span>
                        </div>
                    </div>
                    ${r.content_preview ? `<div class="row-snippet">${r.content_preview}</div>` : ""}
                `;

                row.addEventListener("click", () => {
                    selectRow(idx);
                    logFileAccessAndLaunch(r.filepath);
                });

                resultsList.appendChild(row);
                currentRows.push(row);
            });

            // Default selection to first item
            if (currentRows.length > 0) {
                selectRow(0);
            }
        }
    } catch (e) {
        console.error("Search request failed:", e);
    }
}

// 8. Keyboard Selection Helpers
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

// 9. Event Listeners & Keyboard Navigation
let debounceTimer;
searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(executeSearch, 200);
});

// Keyboard controls: Up, Down, Enter, Escape
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
            if (path) {
                logFileAccessAndLaunch(path);
            }
        }
    } else if (e.key === "Escape") {
        if (searchInput.value) {
            e.preventDefault();
            searchInput.value = "";
            loadRecommendations();
        }
    }
});

if (suggestionsToggle) {
    suggestionsToggle.addEventListener("change", () => {
        localStorage.setItem("compass_show_suggestions", suggestionsToggle.checked ? "true" : "false");
        if (!searchInput.value.trim()) {
            loadRecommendations();
        }
    });
}

btnScan.addEventListener("click", () => triggerScan(false));
btnScanForce.addEventListener("click", () => triggerScan(true));

if (btnAddHorizon) {
    btnAddHorizon.addEventListener("click", addHorizon);
}

scanPathInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        addHorizon();
    }
});

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
    updateDashboardStats();
    loadHorizons();

    // Default suggestions to false (clean view) unless user previously enabled it
    const savedSuggestions = localStorage.getItem("compass_show_suggestions");
    if (suggestionsToggle) {
        suggestionsToggle.checked = savedSuggestions === "true";
    }

    loadRecommendations();
});
