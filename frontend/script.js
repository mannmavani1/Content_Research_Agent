const API_URL = ""; 
let currentMode = "chat";

// ==========================================
// 1. INITIALIZATION & AUTO-RESET
// ==========================================
window.addEventListener('DOMContentLoaded', async () => {
    console.log("Page loaded, clearing old session data...");
    try {
        await fetch(`${API_URL}/ingestion/reset`, { method: "POST" });
        showToast("Session reset. Ready for research.", "info");
    } catch (e) {
        console.error("Failed to reset session:", e);
    }
});

// ==========================================
// 2. TOAST NOTIFICATION SYSTEM
// ==========================================
function showToast(message, type = "info") {
    const container = document.getElementById("toast-container");
    const toast = document.createElement("div");
    
    const colors = {
        success: "bg-green-50 text-green-800 border-green-200",
        error: "bg-red-50 text-red-800 border-red-200",
        info: "bg-white text-gray-800 border-gray-200 shadow-lg"
    };
    const icon = { success: "check_circle", error: "error", info: "info" };

    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border ${colors[type]} shadow-sm min-w-[300px] transform transition-all duration-300 translate-x-full opacity-0`;
    toast.innerHTML = `
        <span class="material-symbols-rounded text-lg">${icon[type]}</span>
        <p class="text-sm font-medium">${message}</p>
    `;

    container.appendChild(toast);
    
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
    card.className = "bg-white border border-gray-200 rounded-lg p-3 shadow-sm flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300";
    card.innerHTML = `
        <div class="w-8 h-8 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-rounded text-brand-600 text-lg">description</span>
        </div>
        <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-gray-800 truncate" title="${filename}">${filename}</p>
            <p class="text-[10px] text-green-600 flex items-center gap-1 font-medium">
                <span class="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse"></span> Ready
            </p>
        </div>
    `;
    list.appendChild(card);
    card.scrollIntoView({ behavior: 'smooth', block: 'end' });
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
        
        if (response.ok) {
            showToast(`Indexed ${file.name}`, "success");
            addFileCard(file.name); 
        } else {
            throw new Error(data.detail);
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
        if (response.ok) {
            const data = await response.json();
            showToast("Text snippet indexed", "success");
            document.getElementById("paste-area").value = "";
            addFileCard(data.filename); 
        }
    } catch (e) { showToast("Failed to process text", "error"); }
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
            await fetch(`${API_URL}/ingestion/reset`, { method: "POST" });
            
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
        appendMessage("bot", data.answer);
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
                        class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg transition-all group"
                        title="Download as Markdown">
                    <span class="material-symbols-rounded text-base text-gray-400 group-hover:text-brand-600 transition">download</span>
                    Download Report
                </button>
            </div>
        `;
    }

    div.innerHTML = `
        <div class="w-9 h-9 rounded-xl ${isBot ? "bg-brand-100 text-brand-600" : "bg-gray-200 text-gray-600"} flex items-center justify-center flex-shrink-0 shadow-sm">
            <span class="material-symbols-rounded text-xl">${isBot ? "smart_toy" : "person"}</span>
        </div>
        <div class="flex-1 max-w-3xl">
            <div class="${isBot ? "bg-white border border-gray-100 shadow-sm text-gray-800" : "bg-brand-600 text-white shadow-md"} px-6 py-4 rounded-2xl ${isBot ? "rounded-tl-none" : "rounded-tr-none"} text-[15px] leading-relaxed prose prose-p:my-1 prose-ul:my-1 w-full">
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
        <div class="w-9 h-9 rounded-xl bg-brand-100 text-brand-600 flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-rounded text-xl">smart_toy</span>
        </div>
        <div class="bg-white px-6 py-4 rounded-2xl rounded-tl-none shadow-sm border border-gray-100 flex items-center gap-2">
            <span class="text-sm text-gray-400 font-medium">Thinking</span>
            <div class="flex gap-1">
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