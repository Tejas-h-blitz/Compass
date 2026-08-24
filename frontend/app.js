// Elements Selection
const statFiles = document.querySelector("#stat-files .stat-value");
const statQueries = document.querySelector("#stat-queries .stat-value");
const statLatency = document.querySelector("#stat-latency .stat-value");

const scanPathInput = document.getElementById("scan-path-input");
const btnScan = document.getElementById("btn-scan");
const btnScanForce = document.getElementById("btn-scan-force");
const scanStatusDiv = document.getElementById("scan-status");
const scanStatusText = document.getElementById("scan-status-text");
const scanResultDiv = document.getElementById("scan-result");
const scanResultDetails = document.getElementById("scan-result-details");

const searchInput = document.getElementById("search-input");
const personalizeToggle = document.getElementById("personalize-toggle");

const routerFeedbackPanel = document.getElementById("router-feedback-panel");
const routerStrategyBadge = document.getElementById("router-strategy-badge");
const routerLatencyValue = document.getElementById("router-latency-value");
const routerSavingsValue = document.getElementById("router-savings-value");
const computeSavingsContainer = document.getElementById("compute-savings-container");

const resultsCountText = document.getElementById("results-count-text");
const resultsList = document.getElementById("results-list");

// Global stats values for calculation
let avgHybridLatency = 25.0; // Benchmark reference for compute savings calculation

// 1. Format Helper functions
function formatBytes(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
}

function formatDate(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

function getFileIcon(fileType) {
    const ext = fileType.toLowerCase();
    if (ext === ".pdf") {
        return `
            <svg class="file-icon-svg pdf-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <path d="M9 15h3a2 2 0 0 0 0-4H9v6"></path>
            </svg>
        `;
    }
    if (ext === ".docx") {
        return `
            <svg class="file-icon-svg docx-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="9" y1="12" x2="15" y2="12"></line>
                <line x1="9" y1="16" x2="15" y2="16"></line>
            </svg>
        `;
    }
    if (ext === ".txt" || ext === ".md") {
        return `
            <svg class="file-icon-svg text-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="9" y1="12" x2="15" y2="12"></line>
                <line x1="9" y1="16" x2="15" y2="16"></line>
                <line x1="9" y1="9" x2="10" y2="9"></line>
            </svg>
        `;
    }
    if ([".py", ".js", ".html", ".css", ".java", ".c", ".cpp", ".h", ".json", ".yaml", ".yml"].includes(ext)) {
        return `
            <svg class="file-icon-svg code-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <polyline points="8 13 6 15 8 17"></polyline>
                <polyline points="12 17 14 15 12 13"></polyline>
            </svg>
        `;
    }
    return `
        <svg class="file-icon-svg folder-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
        </svg>
    `;
}

// 2. Fetch and Update App Stats Dashboard
async function updateDashboardStats() {
    try {
        const response = await fetch("/api/stats");
        if (response.ok) {
            const data = await response.json();
            statFiles.textContent = data.total_files;
            statQueries.textContent = data.total_queries;
            statLatency.textContent = data.avg_latency_ms + " ms";
            // If we have actual queries, update our local average reference
            if (data.avg_latency_ms > 0) {
                // Approximate hybrid average to compile dynamic savings
                avgHybridLatency = Math.max(data.avg_latency_ms * 1.5, 25.0);
            }
        }
    } catch (e) {
        console.error("Failed to load dashboard statistics:", e);
    }
}

// 3. Trigger Local Directory Scanning
async function triggerScan(force = false) {
    const path = scanPathInput.value.trim();
    if (!path) {
        alert("Please enter a valid directory path first.");
        return;
    }

    // Toggle scanning states
    scanStatusDiv.classList.remove("hidden");
    scanStatusText.textContent = force ? "Force re-indexing directory..." : "Scanning directory...";
    scanResultDiv.classList.add("hidden");
    btnScan.disabled = true;
    btnScanForce.disabled = true;

    try {
        const response = await fetch("/api/scan", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ directory_path: path, force: force })
        });

        if (response.ok) {
            const data = await response.json();
            const stats = data.stats;
            scanResultDetails.textContent = `Scanned: ${stats.scanned} | Updated: ${stats.updated} | Pruned: ${stats.pruned}`;
            scanResultDiv.classList.remove("hidden");
        } else {
            const err = await response.json();
            alert(`Scanning failed: ${err.detail || "Unknown error"}`);
        }
    } catch (e) {
        alert(`Request error: ${e.message}`);
    } finally {
        scanStatusDiv.classList.add("hidden");
        btnScan.disabled = false;
        btnScanForce.disabled = false;
        // Refresh counts
        updateDashboardStats();
    }
}

// 4. Log User Access & Launch File Locally
async function logFileAccessAndLaunch(filepath) {
    try {
        const response = await fetch("/api/log-access", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ filepath: filepath })
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log("Logged and launched file:", data.filepath, "Success:", data.launched);
            // Refresh access logs in backend for next search re-ranking
            updateDashboardStats();
            // Re-run search to show the updated personalization score immediately in the UI!
            executeSearch();
        }
    } catch (e) {
        console.error("Failed to log file access:", e);
    }
}

// 5. Execute Search Query Routing
async function executeSearch() {
    const query = searchInput.value.trim();
    const personalize = personalizeToggle.checked;

    if (!query) {
        // Reset to placeholder state
        resultsCountText.textContent = "Type to begin search...";
        routerFeedbackPanel.classList.add("hidden");
        resultsList.innerHTML = `
            <div class="placeholder-state">
                <div class="placeholder-icon-container">
                    <svg class="placeholder-svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="11" cy="11" r="8"></circle>
                        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
                        <line x1="8" y1="11" x2="14" y2="11"></line>
                        <line x1="11" y1="8" x2="11" y2="14"></line>
                    </svg>
                </div>
                <h3>Index folder and type a query above to start searching.</h3>
                <p>Try standard search (filename, short words) or semantic search (marker phrases like "something about vector embeddings").</p>
            </div>
        `;
        return;
    }

    try {
        const response = await fetch(`/api/search?query=${encodeURIComponent(query)}&personalize=${personalize}`);
        if (response.ok) {
            const data = await response.json();
            
            // Render performance metrics
            routerFeedbackPanel.classList.remove("hidden");
            
            const strategy = data.strategy_chosen;
            routerStrategyBadge.textContent = strategy;
            routerStrategyBadge.className = "badge"; // Reset classes
            
            if (strategy === "keyword") routerStrategyBadge.classList.add("badge-keyword");
            else if (strategy === "semantic") routerStrategyBadge.classList.add("badge-semantic");
            else if (strategy === "hybrid") routerStrategyBadge.classList.add("badge-hybrid");
            
            routerLatencyValue.textContent = `${data.latency_ms.toFixed(1)} ms`;
            
            // Calculate compute time savings vs Always-Hybrid
            // If strategy is not hybrid, we saved computing time!
            if (strategy !== "hybrid") {
                computeSavingsContainer.classList.remove("hidden");
                const savingsPct = Math.max(0, ((avgHybridLatency - data.latency_ms) / avgHybridLatency) * 100);
                routerSavingsValue.textContent = `${savingsPct.toFixed(0)}% saved`;
            } else {
                computeSavingsContainer.classList.add("hidden");
            }
            
            // Render Results Cards
            const results = data.results;
            resultsCountText.textContent = `Found ${results.length} relevant files in ${data.latency_ms.toFixed(1)} ms:`;
            
            if (results.length === 0) {
                resultsList.innerHTML = `
                <div class="placeholder-state">
                    <div class="placeholder-icon-container">
                        <svg class="placeholder-svg" viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="22 12 16 12 14 15 10 15 8 12 2 12"></polyline>
                            <path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"></path>
                        </svg>
                    </div>
                    <h3>No matching files found.</h3>
                    <p>Try broadening your query terms, using keywords, or verifying your directory scan.</p>
                </div>
            `;
                return;
            }
            
            resultsList.innerHTML = ""; // Clear list
            results.forEach(r => {
                const card = document.createElement("div");
                card.className = "result-card";
                
                // Construct HTML contents
                const icon = getFileIcon(r.file_type);
                const sizeText = formatBytes(r.file_size);
                const modifiedText = formatDate(r.modified_at);
                
                // Determine whether personalization details apply
                const hasPersonalization = r.explanation.includes("Personalized Boost");
                const isColdStart = r.explanation.includes("Cold-start");
                
                let personalizationBadgeHtml = "";
                if (hasPersonalization) {
                    // Extract detail strings using regex or parsing from explanation
                    const matches = r.explanation.match(/Personalized Boost:\s*([+-]\d+\.\d+)\s*\((.*?)\)\]/);
                    const boostDetails = matches ? matches[2] : "boosted";
                    personalizationBadgeHtml = `
                        <div class="personalization-details">
                            <svg class="badge-icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path>
                            </svg>
                            <span>Personalized: ${boostDetails}</span>
                        </div>
                    `;
                } else if (isColdStart) {
                    personalizationBadgeHtml = `
                        <div class="personalization-details-cold">
                            <svg class="badge-icon-svg" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="2" y1="12" x2="22" y2="12"></line>
                                <line x1="12" y1="2" x2="12" y2="22"></line>
                                <path d="m20 16-4-4 4-4"></path>
                                <path d="m4 8 4 4-4 4"></path>
                                <path d="m16 4-4 4-4-4"></path>
                                <path d="m8 20 4-4 4 4"></path>
                            </svg>
                            <span>Cold-Start: Not yet opened</span>
                        </div>
                    `;
                }
                
                card.innerHTML = `
                    <div class="result-header">
                        <div class="file-info">
                            <span class="file-icon">${icon}</span>
                            <div class="file-name-container">
                                <span class="file-name">${r.filename}</span>
                                <span class="file-path">${r.filepath}</span>
                            </div>
                        </div>
                        <span class="badge ${r.strategy === 'keyword' ? 'badge-keyword' : r.strategy === 'semantic' ? 'badge-semantic' : 'badge-hybrid'}">${r.strategy}</span>
                    </div>
                    <div class="file-meta-row">
                        <div class="meta-item">Size: <strong>${sizeText}</strong></div>
                        <div class="meta-item">Modified: <strong>${modifiedText}</strong></div>
                        <div class="meta-item">Base Score: <strong>${r.score.toFixed(3)}</strong></div>
                    </div>
                    <div class="match-preview">
                        ${r.content_preview}
                    </div>
                    ${personalizationBadgeHtml}
                `;
                
                // Bind local click to trigger os.startfile in backend
                card.addEventListener("click", () => {
                    logFileAccessAndLaunch(r.filepath);
                });
                
                resultsList.appendChild(card);
            });
        }
    } catch (e) {
        console.error("Search request error:", e);
    }
}

// 6. Bind Debounced Input
let debounceTimer;
searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(executeSearch, 250);
});

personalizeToggle.addEventListener("change", executeSearch);

// Bind scan buttons
btnScan.addEventListener("click", () => triggerScan(false));
btnScanForce.addEventListener("click", () => triggerScan(true));

// Initialize on page load
window.addEventListener("DOMContentLoaded", () => {
    updateDashboardStats();
});
