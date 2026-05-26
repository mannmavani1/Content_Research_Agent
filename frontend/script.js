const API_URL = ""; 
let currentMode = "chat";

// ==========================================
// 1. INITIALIZATION & AUTO-RESET
// ==========================================
window.addEventListener('DOMContentLoaded', async () => {
    console.log("Page loaded, clearing old session data...");
    
    // Request Native Push Notification Permission for a professional background response alert
    if (window.Notification && Notification.permission === "default") {
        Notification.requestPermission();
    }

    try {
        await fetch(`${API_URL}/ingestion/reset`, { method: "POST" });
        showToast("Session reset. Ready for research.", "info");
    } catch (e) {
        console.error("Failed to reset session:", e);
    }
});

// ==========================================
// 2. TOAST NOTIFICATION SYSTEM & PUSH ALERTS
// ==========================================
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    
    const colors = {
        success: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-500/20",
        error: "bg-rose-50 text-rose-800 border-rose-200 dark:bg-rose-500/10 dark:text-rose-300 dark:border-rose-500/20",
        info: "bg-white text-slate-800 border-slate-200 dark:bg-slate-900/90 dark:text-white dark:border-white/10 shadow-2xl backdrop-blur-md"
    };
    const icon = { success: "check_circle", error: "error", info: "info" };

    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border ${colors[type]} shadow-lg min-w-[300px] transform transition-all duration-300 translate-x-full opacity-0`;
    toast.innerHTML = `
        <span class="material-symbols-rounded text-lg">${icon[type]}</span>
        <p class="text-xs font-semibold">${message}</p>
    `;

    container.appendChild(toast);
    
    // Send Native Desktop Push Notification if the tab is hidden or minimized
    if (document.hidden && window.Notification && Notification.permission === "granted") {
        try {
            new Notification("RAG Studio Update", {
                body: message,
                tag: "rag-studio-notification"
            });
        } catch (e) {
            console.error("Failed to fire native push notification:", e);
        }
    }

    // Animate In
    requestAnimationFrame(() => toast.classList.remove("translate-x-full", "opacity-0"));
    
    // Animate Out after 4s
    setTimeout(() => {
        toast.classList.add("translate-x-full", "opacity-0");
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ==========================================
// 3. SIDEBAR FILE MANAGEMENT
// ==========================================
function addFileCard(filename) {
    const list = document.getElementById("file-list");
    const title = document.getElementById("file-list-title");
    
    title.classList.remove("hidden");

    const card = document.createElement("div");
    card.className = "glass-card border border-slate-200 dark:border-white/5 rounded-xl p-3 flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300 hover:border-brand-500/30 transition-all group/card relative overflow-hidden";
    card.innerHTML = `
        <div class="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-rounded text-brand-600 dark:text-brand-400 text-base">description</span>
        </div>
        <div class="flex-1 min-w-0">
            <p class="text-xs font-semibold text-slate-700 dark:text-slate-100 truncate pr-6" title="${filename}">${filename}</p>
            <p class="text-[9px] text-emerald-600 dark:text-emerald-400 flex items-center gap-1 font-bold">
                <span class="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-pulse"></span> Ready
            </p>
        </div>
        <button onclick="deleteFileWorkspace(event, '${filename}', this.closest('.glass-card'))" 
                class="absolute right-3.5 top-1/2 -translate-y-1/2 p-1.5 rounded-lg text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 opacity-0 group-hover/card:opacity-100 transition-all duration-200" 
                title="Remove File">
            <span class="material-symbols-rounded text-base">delete</span>
        </button>
    `;
    list.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'end' });
}

async function deleteFileWorkspace(event, filename, cardElement) {
    event.stopPropagation();
    
    const result = await Swal.fire({
        title: 'Delete Document?',
        text: `Are you sure you want to remove ${filename} from your workspace knowledge base?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444', 
        cancelButtonColor: '#1f2937',
        confirmButtonText: 'Delete',
        cancelButtonText: 'Cancel',
        background: '#ffffff',
        color: '#1f2937',
        customClass: {
            popup: 'rounded-2xl shadow-2xl border border-gray-100 font-sans',
            title: 'text-xl font-bold text-gray-800',
            htmlContainer: 'text-sm text-gray-500',
            confirmButton: 'rounded-xl px-5 py-2.5 text-sm font-bold shadow-lg hover:shadow-red-500/30 transition-all',
            cancelButton: 'rounded-xl px-5 py-2.5 text-sm font-medium hover:bg-gray-100 transition-all'
        }
    });

    if (result.isConfirmed) {
        showToast(`Removing ${filename}...`, "info");
        try {
            const response = await fetch(`${API_URL}/ingestion/file?filename=${encodeURIComponent(filename)}`, {
                method: "DELETE"
            });
            const data = await response.json();
            
            if (response.ok && data.status === 200) {
                showToast(data.message, "success");
                
                // Animate the card slide out and remove it
                cardElement.classList.add("translate-x-full", "opacity-0");
                setTimeout(() => {
                    cardElement.remove();
                    
                    // Hide header list if empty
                    const list = document.getElementById("file-list");
                    const title = document.getElementById("file-list-title");
                    if (list.children.length === 0) {
                        title.classList.add("hidden");
                    }
                }, 300);
            } else {
                throw new Error(data.message || "Failed to delete file from workspace");
            }
        } catch (error) {
            showToast(error.message, "error");
        }
    }
}

// ==========================================
// 4. INGESTION (UPLOAD & PASTE)
// ==========================================
async function handleFileUpload(files) {
    if (files.length === 0) return;
    const file = files[0];
    const formData = new FormData();
    formData.append("file", file);

    showToast("Uploading and indexing...", "info");

    try {
        const response = await fetch(`${API_URL}/ingestion/upload`, { method: "POST", body: formData });
        const data = await response.json();
        
        if (response.ok && data.status === 200) {
            showToast(data.message, "success");
            addFileCard(data.data.filename); 
        } else {
            throw new Error(data.message || "Failed to upload file");
        }
    } catch (error) {
        showToast(error.message, "error");
    }
}

async function handlePaste() {
    const text = document.getElementById("paste-area").value;
    if (!text.trim()) { showToast("Please enter some text", "error"); return; }
    
    showToast("Processing text snippet...", "info");

    try {
        const response = await fetch(`${API_URL}/ingestion/paste`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: text })
        });
        const data = await response.json();
        if (response.ok && data.status === 200) {
            showToast(data.message, "success");
            document.getElementById("paste-area").value = "";
            addFileCard(data.data.filename); 
        } else {
            throw new Error(data.message || "Failed to process text");
        }
    } catch (e) { showToast(e.message, "error"); }
}

// ==========================================
// 5. SESSION RESET (SWEETALERT2)
// ==========================================
async function resetSession() {
    const result = await Swal.fire({
        title: 'Clear Workspace?',
        text: "This will remove all uploaded documents and chat history.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#ef4444', 
        cancelButtonColor: '#1f2937',
        confirmButtonText: 'Yes, clear it',
        cancelButtonText: 'Cancel',
        background: '#ffffff',
        color: '#1f2937',
        iconColor: '#ef4444',
        reverseButtons: true,
        backdrop: true, // CSS Blur effect
        customClass: {
            popup: 'rounded-2xl shadow-2xl border border-gray-100 font-sans',
            title: 'text-xl font-bold text-gray-800',
            htmlContainer: 'text-sm text-gray-500',
            confirmButton: 'rounded-xl px-5 py-2.5 text-sm font-bold shadow-lg hover:shadow-red-500/30 transition-all',
            cancelButton: 'rounded-xl px-5 py-2.5 text-sm font-medium hover:bg-gray-100 transition-all'
        }
    });

    if (result.isConfirmed) {
        Swal.fire({
            title: 'Cleaning up...',
            html: '<span class="text-xs text-gray-400">This may take a second</span>',
            didOpen: () => { Swal.showLoading() },
            background: 'rgba(255, 255, 255, 0.9)', 
            backdrop: true,
            allowOutsideClick: false,
            showConfirmButton: false,
            customClass: { popup: 'rounded-2xl' }
        });

        try {
            const response = await fetch(`${API_URL}/ingestion/reset`, { method: "POST" });
            const data = await response.json();
            if (!response.ok || data.status !== 200) throw new Error(data.message || "Could not reset session.");
            
            // UI Cleanup
            document.getElementById("chat-history").innerHTML = "";
            document.getElementById("file-list").innerHTML = ""; 
            document.getElementById("file-list-title").classList.add("hidden");
            
            // Re-add welcome screen
            const history = document.getElementById("chat-history");
            history.innerHTML = `
                <div class="flex flex-col items-center justify-center h-full text-center space-y-4 opacity-60 animate-pulse" id="welcome-screen">
                    <div class="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mb-2">
                        <span class="material-symbols-rounded text-gray-400 text-4xl">smart_toy</span>
                    </div>
                    <h2 class="text-xl font-semibold text-gray-700">What shall we analyze today?</h2>
                    <p class="text-sm text-gray-500 max-w-md">Upload a document to unlock specialized tools like Summarization, Comparison, and Data Extraction.</p>
                </div>
            `;
            
            Swal.fire({
                icon: 'success',
                title: 'Workspace Cleared',
                toast: true,
                position: 'top-end',
                showConfirmButton: false,
                timer: 2000,
                timerProgressBar: true,
                customClass: { popup: 'rounded-xl shadow-lg border border-green-100 flex items-center gap-2', title: 'text-sm font-bold text-gray-800' }
            });

        } catch (e) {
            Swal.fire({ icon: 'error', title: 'Error', text: 'Could not reset session.', confirmButtonColor: '#3b82f6', customClass: { popup: 'rounded-2xl' } });
        }
    }
}

// ==========================================
// 6. MODE SELECTION
// ==========================================
function setMode(mode) {
    currentMode = mode;
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove('bg-gray-900', 'text-white', 'shadow-lg', 'ring-2');
        btn.classList.add('bg-white', 'text-gray-600', 'border', 'border-gray-200');
    });
    const activeBtn = document.querySelector(`.mode-btn[data-mode="${mode}"]`);
    activeBtn.classList.remove('bg-white', 'text-gray-600', 'border', 'border-gray-200');
    activeBtn.classList.add('bg-gray-900', 'text-white', 'shadow-lg', 'ring-2', 'ring-gray-900', 'ring-offset-2');

    const labels = {
        chat: "Auto Routing (AI Decides)",
        summarize: "Strict Summarization",
        compare: "Multi-Doc Comparison",
        extract: "Structured Data Extraction",
        insight: "Strategic Insights"
    };
    document.getElementById("mode-label").textContent = labels[mode];
    showToast(`Switched to ${mode.charAt(0).toUpperCase() + mode.slice(1)} mode`, "info");
}

// ==========================================
// 7. CHAT LOGIC
// ==========================================
function handleEnter(e) { if (e.key === "Enter") sendMessage(); }

async function sendMessage() {
    const inputField = document.getElementById("user-input");
    const message = inputField.value.trim();
    if (!message) return;

    const welcome = document.getElementById("welcome-screen");
    if (welcome) welcome.remove();

    appendMessage("user", message);
    inputField.value = "";
    const loadingId = appendLoading();

    try {
        const endpoint = `${API_URL}/tools/${currentMode}`;
        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: message })
        });
        const data = await response.json();
        removeLoading(loadingId);
        
        if (response.ok && data.status === 200) {
            appendMessage("bot", data.data.answer);
        } else {
            appendMessage("bot", "**Error:** " + (data.message || "Unknown error"));
            showToast(data.message || "Server error", "error");
        }
    } catch (error) {
        removeLoading(loadingId);
        appendMessage("bot", "**Error:** Could not connect to the agent.");
        showToast("Server error", "error");
    }
}

// ==========================================
// 8. UI HELPERS (APPEND MESSAGE & LOADING)
// ==========================================
function appendMessage(role, text) {
    const history = document.getElementById("chat-history");
    const isBot = role === "bot";
    const div = document.createElement("div");
    
    div.className = `msg-animate flex gap-4 max-w-4xl mx-auto ${isBot ? "" : "flex-row-reverse"}`;
    const contentHtml = isBot ? marked.parse(text) : text.replace(/\n/g, '<br>');

    // Download Button Logic
    let downloadBtn = "";
    if (isBot) {
        downloadBtn = `
            <div class="flex justify-end mt-2">
                <button onclick="downloadReport('${encodeURIComponent(text)}')" 
                        class="flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold text-slate-400 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-brand-500/20 rounded-lg transition-all group"
                        title="Download as Markdown">
                    <span class="material-symbols-rounded text-sm text-slate-500 group-hover:text-brand-400 transition">download</span>
                    Download Report
                </button>
            </div>
        `;
    }

    div.innerHTML = `
        <div class="w-9 h-9 rounded-xl ${isBot ? "bg-brand-500/10 border border-brand-500/20 text-brand-400" : "bg-slate-800 border border-white/5 text-slate-300"} flex items-center justify-center flex-shrink-0 shadow-md">
            <span class="material-symbols-rounded text-lg">${isBot ? "terminal" : "person"}</span>
        </div>
        <div class="flex-1 max-w-3xl">
            <div class="${isBot ? "glass-card border border-white/5 text-slate-200" : "bg-gradient-to-r from-brand-600 to-indigo-600 text-white shadow-xl shadow-brand-600/10"} px-5 py-4 rounded-2xl ${isBot ? "rounded-tl-none" : "rounded-tr-none"} text-[13px] leading-relaxed prose prose-p:my-1 prose-ul:my-1 w-full">
                ${contentHtml}
            </div>
            ${downloadBtn}
        </div>
    `;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
}

function appendLoading() {
    const history = document.getElementById("chat-history");
    const id = "loading-" + Date.now();
    const div = document.createElement("div");
    div.id = id;
    div.className = "msg-animate flex gap-4 max-w-4xl mx-auto";
    div.innerHTML = `
        <div class="w-9 h-9 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-rounded text-lg">terminal</span>
        </div>
        <div class="glass-card px-5 py-4 rounded-2xl rounded-tl-none border border-white/5 flex items-center gap-2">
            <span class="text-xs text-slate-400 font-bold uppercase tracking-wider">Analyzing</span>
            <div class="flex gap-1.5">
                <div class="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce"></div>
                <div class="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                <div class="w-1.5 h-1.5 bg-brand-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
            </div>
        </div>
    `;
    history.appendChild(div);
    history.scrollTop = history.scrollHeight;
    return id;
}

function removeLoading(id) { const el = document.getElementById(id); if (el) el.remove(); }

// ==========================================
// 9. DOWNLOAD HELPER
// ==========================================
function downloadReport(encodedText) {
    try {
        const text = decodeURIComponent(encodedText);
        const blob = new Blob([text], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement("a");
        a.href = url;
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        a.download = `Research_Report_${timestamp}.md`;
        
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        showToast("Report downloaded successfully", "success");
    } catch (e) {
        console.error(e);
        showToast("Failed to download report", "error");
    }
}

// ==========================================
// 10. SAMPLE PROMPT TRIGGERS & DRAG-DROP
// ==========================================
function clickSamplePrompt(text) {
    const input = document.getElementById("user-input");
    if (!input) return;
    input.value = text;
    sendMessage();
}

window.addEventListener('dragenter', (e) => {
    e.preventDefault();
    const overlay = document.getElementById('drag-overlay');
    const card = document.getElementById('drag-overlay-card');
    if (overlay && card) {
        overlay.classList.remove('opacity-0', 'pointer-events-none', 'scale-95');
        card.classList.remove('scale-95');
    }
});

window.addEventListener('dragover', (e) => {
    e.preventDefault();
});

window.addEventListener('dragleave', (e) => {
    if (e.relatedTarget === null || e.fromElement === null) {
        dismissDragOverlay();
    }
});

window.addEventListener('drop', (e) => {
    e.preventDefault();
    dismissDragOverlay();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileUpload(e.dataTransfer.files);
    }
});

function dismissDragOverlay() {
    const overlay = document.getElementById('drag-overlay');
    const card = document.getElementById('drag-overlay-card');
    if (overlay && card) {
        overlay.classList.add('opacity-0', 'pointer-events-none', 'scale-95');
        card.classList.add('scale-95');
    }
}