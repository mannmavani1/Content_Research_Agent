const API_URL = "";
let currentMode = "chat";
let currentConversationId = null;

// WebSocket connection management variables
let chatSocket = null;
let activeStreamMessageId = null;
let activeStreamText = "";
let activeLoadingId = null;

// Inject cursor typing styles dynamically
(function injectCursorStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .stream-cursor {
            display: inline-block;
            width: 7px;
            height: 15px;
            background-color: #8b5cf6;
            border-radius: 2px;
            margin-left: 4px;
            vertical-align: -2px;
            animation: cursorBlink 0.8s infinite;
        }
        .dark .stream-cursor {
            background-color: #a78bfa;
        }
        @keyframes cursorBlink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }
    `;
    document.head.appendChild(style);
})();

function connectWebSocket() {
    if (chatSocket && (chatSocket.readyState === WebSocket.OPEN || chatSocket.readyState === WebSocket.CONNECTING)) {
        return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    let wsHost = window.location.host;
    if (API_URL) {
        try {
            const urlObj = new URL(API_URL);
            wsHost = urlObj.host;
        } catch(e) {}
    }
    const wsUrl = `${protocol}//${wsHost}/tools/ws/chat`;
    console.log("Connecting to WebSocket:", wsUrl);

    chatSocket = new WebSocket(wsUrl);

    chatSocket.onopen = () => {
        console.log("WebSocket connection established");
    };

    chatSocket.onclose = (event) => {
        console.log("WebSocket connection closed, code =", event.code, "reason =", event.reason);
        // Do not reconnect on auth violations (HTTP status mapped to 1008 policy violation)
        if (event.code !== 1008) {
            setTimeout(connectWebSocket, 3000);
        }
    };

    chatSocket.onerror = (error) => {
        console.error("WebSocket error:", error);
    };

    chatSocket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === "start") {
                if (activeLoadingId) {
                    removeLoading(activeLoadingId);
                    activeLoadingId = null;
                }
                activeStreamMessageId = "stream-" + Date.now();
                activeStreamText = "";
                appendBotStreamMessage(activeStreamMessageId);
            } else if (data.type === "chunk") {
                activeStreamText += data.text;
                updateBotStreamMessage(activeStreamMessageId, activeStreamText, false);
            } else if (data.type === "end") {
                updateBotStreamMessage(activeStreamMessageId, data.text || activeStreamText, true);
                activeStreamMessageId = null;
                activeStreamText = "";
            } else if (data.type === "error") {
                if (activeLoadingId) {
                    removeLoading(activeLoadingId);
                    activeLoadingId = null;
                }
                if (activeStreamMessageId) {
                    updateBotStreamMessage(activeStreamMessageId, "**Error:** " + data.message, true);
                    activeStreamMessageId = null;
                } else {
                    appendMessage("bot", "**Error:** " + data.message);
                }
                showToast(data.message || "Execution error", "error");
            }
        } catch (e) {
            console.error("Error processing websocket message:", e);
        }
    };
}

// ==========================================
// 1. INITIALIZATION & AUTO-RESET
// ==========================================
window.addEventListener('DOMContentLoaded', async () => {
    console.log("Page loaded, fetching session data...");

    if (window.Notification && Notification.permission === "default") {
        Notification.requestPermission();
    }

    try {
        // Check authentication status first
        const authResponse = await fetch(`${API_URL}/auth/me`);
        if (!authResponse.ok) {
            // Not authenticated, show login overlay
            document.getElementById('login-overlay').classList.remove('hidden');
            return; // Stop initialization
        }

        // Authenticated! Show user profile and continue
        const userData = await authResponse.json();
        const userNameEl = document.getElementById('user-name');
        if (userNameEl && userData.first_name) {
            userNameEl.textContent = userData.first_name;
        }
        document.getElementById('user-profile').classList.remove('hidden');
        document.getElementById('login-overlay').classList.add('hidden');

        await loadConversations();
        connectWebSocket();
    } catch (e) {
        console.error("Failed to load session:", e);
    }
});

// ==========================================

// ==========================================
// 1.5 CONVERSATION MANAGEMENT
// ==========================================
async function loadConversations() {
    try {
        const response = await fetch(`${API_URL}/tools/conversations`);
        const data = await response.json();
        const list = document.getElementById("conversation-list");
        if (!list) return;
        list.innerHTML = "";

        if (data.data && data.data.length > 0) {
            data.data.forEach(conv => {
                const wrapper = document.createElement("div");
                wrapper.className = `group flex items-center justify-between p-2 rounded-lg transition-all duration-200 cursor-pointer ${currentConversationId === conv.id ? 'bg-brand-50 border border-brand-200 dark:bg-brand-900/20 dark:border-brand-500/30 shadow-sm' : 'hover:bg-gray-50 dark:hover:bg-white/5 border border-transparent'}`;

                const btn = document.createElement("button");
                btn.className = `flex-1 text-left text-xs font-bold tracking-wider truncate mr-2 ${currentConversationId === conv.id ? 'text-brand-600 dark:text-brand-400' : 'text-gray-500 dark:text-gray-400 group-hover:text-gray-800 dark:group-hover:text-gray-200'}`;
                btn.textContent = conv.title;
                btn.onclick = () => switchConversation(conv.id);

                const actions = document.createElement("div");
                actions.className = "hidden group-hover:flex items-center gap-1 flex-shrink-0";

                const renameBtn = document.createElement("button");
                renameBtn.className = "text-gray-400 hover:text-brand-500 transition-colors p-1";
                renameBtn.innerHTML = '<span class="material-symbols-rounded text-[14px]">edit</span>';
                renameBtn.onclick = (e) => { e.stopPropagation(); renameConversation(conv.id, conv.title); };

                const deleteBtn = document.createElement("button");
                deleteBtn.className = "text-gray-400 hover:text-rose-500 transition-colors p-1";
                deleteBtn.innerHTML = '<span class="material-symbols-rounded text-[14px]">delete</span>';
                deleteBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };

                actions.appendChild(renameBtn);
                actions.appendChild(deleteBtn);

                wrapper.appendChild(btn);
                wrapper.appendChild(actions);
                list.appendChild(wrapper);
            });
            if (!currentConversationId) {
                switchConversation(data.data[0].id);
            }
        } else {
            showStartChatScreen();
        }
    } catch (e) {
        console.error(e);
    }
}

async function renameConversation(id, currentTitle) {
    const { value: newTitle } = await Swal.fire({
        title: 'Rename Chat',
        input: 'text',
        inputValue: currentTitle,
        showCancelButton: true,
        confirmButtonText: 'Save',
        confirmButtonColor: '#8b5cf6',
        inputValidator: (value) => {
            if (!value) return 'You need to write something!';
        }
    });

    if (newTitle && newTitle !== currentTitle) {
        try {
            await fetch(`${API_URL}/tools/conversations/${id}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: newTitle })
            });
            showToast("Chat renamed", "success");
            await loadConversationsWithoutSwitching();
        } catch (e) {
            console.error(e);
        }
    }
}

async function deleteConversation(id) {
    const result = await Swal.fire({
        title: 'Are you sure?',
        text: "This will permanently delete this conversation.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#f43f5e',
        cancelButtonColor: '#8b5cf6',
        confirmButtonText: 'Yes, delete it!'
    });

    if (result.isConfirmed) {
        try {
            await fetch(`${API_URL}/tools/conversations/${id}`, { method: "DELETE" });
            showToast("Chat deleted", "info");

            if (currentConversationId === id) {
                currentConversationId = null;
                await loadConversations();
            } else {
                await loadConversationsWithoutSwitching();
            }
        } catch (e) {
            console.error(e);
        }
    }
}

async function createNewConversation() {
    const { value: title, isDismissed } = await Swal.fire({
        title: 'New Research Chat',
        text: 'Enter a name for this session:',
        input: 'text',
        inputPlaceholder: 'e.g. Market Analysis, Project Research...',
        inputValue: 'New Chat',
        showCancelButton: true,
        confirmButtonText: 'Create Session',
        confirmButtonColor: '#8b5cf6',
        cancelButtonText: 'Cancel',
        cancelButtonColor: '#64748b',
        customClass: {
            popup: 'rounded-2xl dark:bg-slate-900 dark:text-white',
            input: 'rounded-xl text-sm border-slate-300 dark:border-white/10 dark:bg-slate-800 dark:text-white'
        },
        inputValidator: (value) => {
            if (!value || !value.trim()) {
                return 'Please enter a name for the chat session!';
            }
        }
    });

    if (isDismissed || !title) return;

    try {
        const response = await fetch(`${API_URL}/tools/conversations`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: title.trim() })
        });
        const data = await response.json();
        if (data.status === 200) {
            await loadConversations();
            switchConversation(data.data.id);
            showToast(`Created session: "${title.trim()}"`, "success");
        }
    } catch (e) {
        console.error(e);
        showToast("Failed to create conversation", "error");
    }
}

async function switchConversation(id) {
    currentConversationId = id;
    const history = document.getElementById("chat-history");
    history.innerHTML = "";


    // Enable inputs since a chat is active
    updateInputsState(true);

    const panel = document.getElementById("chat-input-panel");
    if (panel) panel.classList.remove("hidden");

    await loadConversationsWithoutSwitching();

    try {
        const response = await fetch(`${API_URL}/tools/conversations/${id}`);
        const data = await response.json();
        if (data.status === 200 && data.data) {
            data.data.forEach(msg => {
                appendMessage(msg.role, msg.content, false);
            });
        }
    } catch (e) {
        console.error(e);
    }

    // Fetch and populate active files for this conversation
    await fetchActiveFiles(id);
}

async function fetchActiveFiles(conversationId) {
    if (!conversationId) return;

    const list = document.getElementById("file-list");
    const title = document.getElementById("file-list-title");

    // Clear current list
    list.innerHTML = "";
    title.classList.add("hidden");

    try {
        const response = await fetch(`${API_URL}/ingestion/files/${conversationId}`);
        const data = await response.json();
        if (data.status === 200 && data.data && data.data.files.length > 0) {
            title.classList.remove("hidden");
            data.data.files.forEach(filename => {
                addFileCard(filename);
            });
        }
    } catch (e) {
        console.error("Failed to fetch active files:", e);
    }
}

function showStartChatScreen() {
    currentConversationId = null;

    const history = document.getElementById("chat-history");
    history.innerHTML = `
        <div class="flex flex-col items-center justify-center h-full text-center max-w-2xl mx-auto space-y-6" id="welcome-screen">
            <div class="w-16 h-16 bg-brand-500/5 dark:bg-gradient-to-tr dark:from-brand-600/20 dark:to-indigo-500/20 border border-brand-500/20 dark:border-brand-500/30 rounded-2xl flex items-center justify-center shadow-inner animate-pulse">
                <span class="material-symbols-rounded text-brand-600 dark:text-brand-400 text-3xl">chat</span>
            </div>
            <div class="space-y-2">
                <h2 class="font-display font-bold text-2xl text-slate-800 dark:text-white tracking-wide">Start a New Research Session</h2>
                <p class="text-xs text-slate-500 dark:text-slate-400 leading-relaxed max-w-md mx-auto">Create a workspace session to begin uploading files, pasting context, and running analyses.</p>
            </div>
            
            <button onclick="createNewConversation()" class="flex items-center gap-2 px-6 py-3 rounded-2xl bg-brand-600 hover:bg-brand-700 text-white font-bold text-xs shadow-md shadow-brand-600/20 active:scale-95 transition-all">
                <span class="material-symbols-rounded text-sm">add</span>
                Start Chat
            </button>
        </div>
    `;

    const fileTitle = document.getElementById("file-list-title");
    if (fileTitle) fileTitle.classList.add("hidden");
    const fileList = document.getElementById("file-list");
    if (fileList) fileList.innerHTML = "";

    const panel = document.getElementById("chat-input-panel");
    if (panel) panel.classList.add("hidden");

    updateInputsState(false);
}

function updateInputsState(hasChat) {
    const userInput = document.getElementById("user-input");
    const sendBtn = userInput ? userInput.nextElementSibling : null;
    const dropZone = document.getElementById("drop-zone");
    const pasteArea = document.getElementById("paste-area");
    const pasteBtn = document.getElementById("paste-submit");

    if (userInput) {
        userInput.disabled = !hasChat;
        if (!hasChat) {
            userInput.placeholder = "Start a chat session first to begin...";
        } else {
            userInput.placeholder = "Formulate queries or tasks for your loaded knowledge...";
        }
    }
    if (sendBtn) {
        sendBtn.disabled = !hasChat;
        if (!hasChat) {
            sendBtn.classList.add("opacity-50", "pointer-events-none");
        } else {
            sendBtn.classList.remove("opacity-50", "pointer-events-none");
        }
    }

    if (dropZone) {
        if (!hasChat) {
            dropZone.classList.add("opacity-40", "pointer-events-none");
        } else {
            dropZone.classList.remove("opacity-40", "pointer-events-none");
        }
    }

    if (pasteArea) {
        pasteArea.disabled = !hasChat;
        if (!hasChat) {
            pasteArea.placeholder = "Start a chat session first to paste data...";
        } else {
            pasteArea.placeholder = "Paste structural data, notes, or articles here...";
        }
    }
    if (pasteBtn) {
        if (!hasChat) {
            pasteBtn.classList.add("opacity-50", "pointer-events-none");
        } else {
            pasteBtn.classList.remove("opacity-50", "pointer-events-none");
        }
    }
}

async function loadConversationsWithoutSwitching() {
    try {
        const response = await fetch(`${API_URL}/tools/conversations`);
        const data = await response.json();
        const list = document.getElementById("conversation-list");
        if (!list) return;
        list.innerHTML = "";

        if (data.data) {
            data.data.forEach(conv => {
                const wrapper = document.createElement("div");
                wrapper.className = `group flex items-center justify-between p-2 rounded-lg transition-all duration-200 cursor-pointer ${currentConversationId === conv.id ? 'bg-brand-50 border border-brand-200 dark:bg-brand-900/20 dark:border-brand-500/30 shadow-sm' : 'hover:bg-gray-50 dark:hover:bg-white/5 border border-transparent'}`;

                const btn = document.createElement("button");
                btn.className = `flex-1 text-left text-xs font-bold tracking-wider truncate mr-2 ${currentConversationId === conv.id ? 'text-brand-600 dark:text-brand-400' : 'text-gray-500 dark:text-gray-400 group-hover:text-gray-800 dark:group-hover:text-gray-200'}`;
                btn.textContent = conv.title;
                btn.onclick = () => switchConversation(conv.id);

                const actions = document.createElement("div");
                actions.className = "hidden group-hover:flex items-center gap-1 flex-shrink-0";

                const renameBtn = document.createElement("button");
                renameBtn.className = "text-gray-400 hover:text-brand-500 transition-colors p-1";
                renameBtn.innerHTML = '<span class="material-symbols-rounded text-[14px]">edit</span>';
                renameBtn.onclick = (e) => { e.stopPropagation(); renameConversation(conv.id, conv.title); };

                const deleteBtn = document.createElement("button");
                deleteBtn.className = "text-gray-400 hover:text-rose-500 transition-colors p-1";
                deleteBtn.innerHTML = '<span class="material-symbols-rounded text-[14px]">delete</span>';
                deleteBtn.onclick = (e) => { e.stopPropagation(); deleteConversation(conv.id); };

                actions.appendChild(renameBtn);
                actions.appendChild(deleteBtn);

                wrapper.appendChild(btn);
                wrapper.appendChild(actions);
                list.appendChild(wrapper);
            });
        }
    } catch (e) {
        console.error(e);
    }
}

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
            new Notification("Content Research Agent Update", {
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

    if (title) title.classList.remove("hidden");
    if (!list) return;

    // Prevent duplicate DOM cards
    const existing = Array.from(list.querySelectorAll("p[title]")).find(p => p.getAttribute("title") === filename);
    if (existing) return;

    const ext = filename.split('.').pop().toLowerCase();
    let icon = "description";
    let iconColorClass = "text-brand-600 dark:text-brand-400";
    let bgColorClass = "bg-brand-500/10 border-brand-500/20";

    if (ext === "pdf") {
        icon = "picture_as_pdf";
        iconColorClass = "text-rose-600 dark:text-rose-400";
        bgColorClass = "bg-rose-500/10 border-rose-500/20";
    } else if (["docx", "doc", "txt", "md"].includes(ext)) {
        icon = "article";
        iconColorClass = "text-blue-600 dark:text-blue-400";
        bgColorClass = "bg-blue-500/10 border-blue-500/20";
    } else if (["xlsx", "xls", "csv"].includes(ext)) {
        icon = "table_chart";
        iconColorClass = "text-emerald-600 dark:text-emerald-400";
        bgColorClass = "bg-emerald-500/10 border-emerald-500/20";
    } else if (ext === "pptx") {
        icon = "slideshow";
        iconColorClass = "text-orange-600 dark:text-orange-400";
        bgColorClass = "bg-orange-500/10 border-orange-500/20";
    } else if (["png", "jpg", "jpeg", "webp", "gif"].includes(ext)) {
        icon = "image";
        iconColorClass = "text-amber-600 dark:text-amber-400";
        bgColorClass = "bg-amber-500/10 border-amber-500/20";
    } else if (["mp3", "wav", "m4a"].includes(ext)) {
        icon = "audiotrack";
        iconColorClass = "text-indigo-600 dark:text-indigo-400";
        bgColorClass = "bg-indigo-500/10 border-indigo-500/20";
    } else if (["mp4", "mov", "mkv"].includes(ext)) {
        icon = "video_library";
        iconColorClass = "text-cyan-600 dark:text-cyan-400";
        bgColorClass = "bg-cyan-500/10 border-cyan-500/20";
    }

    const card = document.createElement("div");
    card.className = "glass-card border border-slate-200 dark:border-white/5 rounded-xl p-3 flex items-center gap-3 animate-in fade-in slide-in-from-bottom-2 duration-300 hover:border-brand-500/30 transition-all group/card relative overflow-hidden";
    card.innerHTML = `
        <div class="w-8 h-8 rounded-lg ${bgColorClass} border flex items-center justify-center flex-shrink-0">
            <span class="material-symbols-rounded ${iconColorClass} text-base">${icon}</span>
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
            let url = `${API_URL}/ingestion/file?filename=${encodeURIComponent(filename)}`;
            if (currentConversationId) {
                url += `&conversation_id=${currentConversationId}`;
            }
            const response = await fetch(url, {
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
let isUploadingFile = false;

async function handleFileUpload(files) {
    if (!files || files.length === 0) return;
    if (isUploadingFile) return;
    isUploadingFile = true;

    const file = files[0];

    // If no conversation is selected, auto-create one first
    if (!currentConversationId) {
        try {
            const resp = await fetch(`${API_URL}/tools/conversations`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: file.name.replace(/\.[^/.]+$/, "") || "New Chat" })
            });
            const convData = await resp.json();
            if (convData.status === 200 && convData.data) {
                currentConversationId = convData.data.id;
                await loadConversationsWithoutSwitching();
                switchConversation(currentConversationId);
            }
        } catch (err) {
            console.error("Failed to auto-create conversation for upload:", err);
        }
    }

    const formData = new FormData();
    formData.append("file", file);
    if (currentConversationId) {
        formData.append("conversation_id", currentConversationId);
    }

    showToast(`Uploading and indexing ${file.name}...`, "info");

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
    } finally {
        isUploadingFile = false;
        const fileInput = document.getElementById("file-upload");
        if (fileInput) fileInput.value = "";
    }
}

async function handlePaste() {
    const text = document.getElementById("paste-area").value;
    if (!text.trim()) { showToast("Please enter some text", "error"); return; }

    // If no conversation is selected, auto-create one first
    if (!currentConversationId) {
        try {
            const resp = await fetch(`${API_URL}/tools/conversations`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ title: "Pasted Context Chat" })
            });
            const convData = await resp.json();
            if (convData.status === 200 && convData.data) {
                currentConversationId = convData.data.id;
                await loadConversationsWithoutSwitching();
                switchConversation(currentConversationId);
            }
        } catch (err) {
            console.error("Failed to auto-create conversation for paste:", err);
        }
    }

    try {
        const bodyData = { text: text };
        if (currentConversationId) {
            bodyData.conversation_id = currentConversationId;
        }

        const response = await fetch(`${API_URL}/ingestion/paste`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(bodyData)
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
            let url = `${API_URL}/ingestion/reset`;
            if (currentConversationId) {
                url += `?conversation_id=${currentConversationId}`;
            }
            const response = await fetch(url, { method: "POST" });
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

    const activeClasses = ['active', 'bg-brand-600', 'bg-brand-500', 'text-white', 'shadow-md', 'shadow-lg', 'shadow-brand-500/25'];
    const inactiveClasses = ['text-slate-600', 'dark:text-slate-400', 'hover:text-slate-900', 'dark:hover:text-white'];

    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.remove(...activeClasses);
        btn.classList.add(...inactiveClasses);
    });

    const activeBtn = document.querySelector(`.mode-btn[data-mode="${mode}"]`);
    if (activeBtn) {
        activeBtn.classList.remove(...inactiveClasses);
        activeBtn.classList.add('active', 'bg-brand-600', 'text-white', 'shadow-md');
    }

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

    if (!chatSocket || chatSocket.readyState !== WebSocket.OPEN) {
        showToast("Connecting to server... Please wait a moment and try again.", "warning");
        connectWebSocket();
        return;
    }

    const welcome = document.getElementById("welcome-screen");
    if (welcome) welcome.remove();

    appendMessage("user", message);
    inputField.value = "";
    activeLoadingId = appendLoading();

    try {
        const payload = { 
            message: message,
            conversation_id: currentConversationId,
            mode: currentMode
        };
        chatSocket.send(JSON.stringify(payload));
    } catch (error) {
        if (activeLoadingId) {
            removeLoading(activeLoadingId);
            activeLoadingId = null;
        }
        appendMessage("bot", "**Error:** Could not connect to the agent.");
        showToast("Failed to send message", "error");
    }
}

function appendBotStreamMessage(id) {
    const history = document.getElementById("chat-history");
    const div = document.createElement("div");
    div.id = id;
    div.className = "flex gap-4 max-w-4xl mx-auto";
    div.innerHTML = `
        <div class="w-9 h-9 rounded-xl bg-brand-500/10 border border-brand-500/20 text-brand-400 flex items-center justify-center flex-shrink-0 shadow-md">
            <span class="material-symbols-rounded text-lg">terminal</span>
        </div>
        <div class="flex-1 min-w-0 max-w-3xl">
            <div class="message-content glass-card border border-white/5 text-slate-200 w-full overflow-hidden px-5 py-4 rounded-2xl rounded-tl-none text-[13px] leading-relaxed prose prose-p:my-1 prose-ul:my-1 break-words">
                <p></p>
            </div>
            <div class="action-panel flex justify-end mt-2 hidden">
                <button class="download-report-btn flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold text-slate-400 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-brand-500/20 rounded-lg transition-all group cursor-pointer"
                        title="Download as Markdown">
                    <span class="material-symbols-rounded text-sm text-slate-500 group-hover:text-brand-400 transition">download</span>
                    Download Report
                </button>
            </div>
        </div>
    `;
    history.appendChild(div);

    // Apply Framer Motion smooth entrance
    if (window.Motion && typeof window.Motion.animate === "function") {
        window.Motion.animate(div, { opacity: [0, 1], y: [10, 0] }, { duration: 0.3, easing: [0.16, 1, 0.3, 1] });
    }

    history.scrollTop = history.scrollHeight;
    return div;
}

let streamRenderRaf = null;
let pendingStreamPayload = null;
let smoothScrollRaf = null;

function triggerSmoothScroll() {
    const history = document.getElementById("chat-history");
    if (!history) return;
    
    const isNearBottom = history.scrollHeight - history.scrollTop - history.clientHeight < 400;
    if (!isNearBottom) return;

    if (smoothScrollRaf) cancelAnimationFrame(smoothScrollRaf);

    const step = () => {
        const target = history.scrollHeight - history.clientHeight;
        const diff = target - history.scrollTop;
        if (diff > 1) {
            history.scrollTop += Math.max(16, Math.ceil(diff * 0.65));
            smoothScrollRaf = requestAnimationFrame(step);
        } else {
            history.scrollTop = target;
            smoothScrollRaf = null;
        }
    };
    smoothScrollRaf = requestAnimationFrame(step);
}

function updateBotStreamMessage(id, text, isDone = false) {
    const div = document.getElementById(id);
    if (!div) return;

    if (isDone) {
        if (streamRenderRaf) {
            cancelAnimationFrame(streamRenderRaf);
            streamRenderRaf = null;
        }
        renderStreamContent(div, text, true);
        return;
    }

    pendingStreamPayload = { div, text };
    if (!streamRenderRaf) {
        streamRenderRaf = requestAnimationFrame(() => {
            streamRenderRaf = null;
            if (pendingStreamPayload) {
                renderStreamContent(pendingStreamPayload.div, pendingStreamPayload.text, false);
            }
        });
    }
}

function renderStreamContent(div, text, isDone) {
    const messageContentDiv = div.querySelector(".message-content");
    const actionPanel = div.querySelector(".action-panel");
    if (!messageContentDiv) return;

    const processedText = prepareMarkdownText(text);

    if (isDone) {
        messageContentDiv.innerHTML = marked.parse(processedText || "*(Empty response)*");

        // Attach interactive styling and lightbox modal click handler to any rendered <img> elements
        messageContentDiv.querySelectorAll("img").forEach(img => {
            img.className = "rounded-2xl border border-slate-200 dark:border-white/10 shadow-lg my-3 max-h-80 max-w-full object-contain cursor-pointer transition-all duration-200 hover:scale-[1.015] hover:shadow-brand-500/20";
            img.title = "Click to view full size";
            img.onclick = () => openImageModal(img.src, img.alt);
        });

        // Show download button with Motion spring animation
        if (actionPanel) {
            actionPanel.classList.remove("hidden");
            if (window.Motion && typeof window.Motion.animate === "function") {
                window.Motion.animate(actionPanel, { opacity: [0, 1], y: [4, 0] }, { duration: 0.25, easing: "ease-out" });
            }
            const downloadBtnEl = actionPanel.querySelector('.download-report-btn');
            if (downloadBtnEl) {
                downloadBtnEl.onclick = () => downloadReportDirect(text);
            }
        }
    } else {
        if (processedText) {
            let parsedHtml = marked.parse(processedText);
            // Append inline cursor safely before closing tag
            if (parsedHtml.includes("</p>")) {
                parsedHtml = parsedHtml.replace(/<\/p>$/, '<span class="stream-cursor"></span></p>');
            } else if (parsedHtml.includes("</li>")) {
                parsedHtml = parsedHtml.replace(/<\/li>$/, '<span class="stream-cursor"></span></li>');
            } else {
                parsedHtml += '<span class="stream-cursor"></span>';
            }
            messageContentDiv.innerHTML = parsedHtml;
        } else {
            messageContentDiv.innerHTML = '<span class="inline-flex items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500 italic"><span class="w-2 h-2 rounded-full bg-brand-500 animate-ping"></span> Thinking & analyzing...</span>';
        }
    }

    triggerSmoothScroll();
}

// ==========================================
// 8. UI HELPERS (APPEND MESSAGE & LOADING)
// ==========================================
function prepareMarkdownText(text) {
    if (!text) return "";
    
    let cleaned = text;
    
    // Check if there is text outside <think>...</think>
    const withoutThink = cleaned.replace(/<think>[\s\S]*?<\/think>/gi, "").replace(/<think>[\s\S]*$/gi, "").trim();
    
    if (withoutThink.length > 0) {
        cleaned = withoutThink;
    } else {
        // Fallback: If content was inside think tags, strip only the tags so text is still visible
        cleaned = cleaned.replace(/<\/?think>/gi, "").trim();
    }
    
    // Strip redundant outer ```markdown ... ``` or ```md ... ``` wrappers if the LLM wrapped the entire answer in a code block
    const outerCodeBlockRegex = /^```(?:markdown|md)?\s*([\s\S]*?)\s*```$/i;
    const match = cleaned.match(outerCodeBlockRegex);
    if (match) {
        cleaned = match[1].trim();
    }
    
    // Pre-process markdown images: replace unencoded spaces and fix relative storage paths
    return cleaned.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (match, alt, url) => {
        let cleanUrl = url.trim().replace(/ /g, '%20');
        if (!cleanUrl.startsWith('http') && !cleanUrl.startsWith('/storage/') && !cleanUrl.startsWith('/static/')) {
            if (cleanUrl.startsWith('/')) {
                cleanUrl = cleanUrl.substring(1);
            }
            cleanUrl = '/storage/' + cleanUrl;
        }
        return `![${alt}](${cleanUrl})`;
    });
}

function openImageModal(src, alt) {
    const modal = document.getElementById("image-modal");
    const img = document.getElementById("image-modal-img");
    const caption = document.getElementById("image-modal-caption");
    if (!modal || !img) return;

    img.src = src;
    caption.textContent = alt || "Keyframe Image";
    modal.classList.remove("hidden");
    setTimeout(() => {
        modal.classList.remove("opacity-0");
    }, 10);
}

function closeImageModal() {
    const modal = document.getElementById("image-modal");
    if (!modal) return;
    modal.classList.add("opacity-0");
    setTimeout(() => {
        modal.classList.add("hidden");
    }, 300);
}

function appendMessage(role, text) {
    const history = document.getElementById("chat-history");
    const isBot = role === "bot";
    const div = document.createElement("div");

    div.className = `msg-animate flex gap-4 max-w-4xl mx-auto ${isBot ? "" : "flex-row-reverse"}`;
    
    const processedText = isBot ? prepareMarkdownText(text) : text;
    const contentHtml = isBot ? marked.parse(processedText) : text.replace(/\n/g, '<br>');

    div.innerHTML = `
        <div class="w-9 h-9 rounded-xl ${isBot ? "bg-brand-500/10 border border-brand-500/20 text-brand-400" : "bg-slate-800 border border-white/5 text-slate-300"} flex items-center justify-center flex-shrink-0 shadow-md">
            <span class="material-symbols-rounded text-lg">${isBot ? "terminal" : "person"}</span>
        </div>
        <div class="${isBot ? "flex-1 min-w-0" : ""} max-w-3xl">
            <div class="${isBot ? "glass-card border border-white/5 text-slate-200 w-full overflow-hidden" : "bg-gradient-to-r from-brand-600 to-indigo-600 text-white shadow-xl shadow-brand-600/10 w-fit ml-auto"} px-5 py-4 rounded-2xl ${isBot ? "rounded-tl-none" : "rounded-tr-none"} text-[13px] leading-relaxed prose prose-p:my-1 prose-ul:my-1 break-words">
                ${contentHtml}
            </div>
            ${isBot ? `
                <div class="flex justify-end mt-2">
                    <button class="download-report-btn flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold text-slate-400 bg-white/5 hover:bg-white/10 border border-white/5 hover:border-brand-500/20 rounded-lg transition-all group cursor-pointer"
                            title="Download as Markdown">
                        <span class="material-symbols-rounded text-sm text-slate-500 group-hover:text-brand-400 transition">download</span>
                        Download Report
                    </button>
                </div>
            ` : ''}
        </div>
    `;
    
    // Bind click event directly to prevent inline onclick string escaping syntax errors
    if (isBot) {
        const downloadBtnEl = div.querySelector('.download-report-btn');
        if (downloadBtnEl) {
            downloadBtnEl.onclick = () => downloadReportDirect(text);
        }
    }

    // Attach interactive styling and lightbox modal click handler to any rendered <img> elements
    div.querySelectorAll("img").forEach(img => {
        img.className = "rounded-2xl border border-slate-200 dark:border-white/10 shadow-lg my-3 max-h-80 max-w-full object-contain cursor-pointer transition-all duration-200 hover:scale-[1.015] hover:shadow-brand-500/20";
        img.title = "Click to view full size";
        img.onclick = () => openImageModal(img.src, img.alt);
    });

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
function downloadReportDirect(text) {
    try {
        if (!text) {
            showToast("No content to download", "error");
            return;
        }
        const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement("a");
        a.href = url;
        const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
        a.download = `Research_Report_${timestamp}.md`;

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        setTimeout(() => URL.revokeObjectURL(url), 1000);

        showToast("Report downloaded successfully", "success");
    } catch (e) {
        console.error("Download failed:", e);
        showToast("Failed to download report", "error");
    }
}

function downloadReport(encodedText) {
    try {
        const text = decodeURIComponent(encodedText);
        downloadReportDirect(text);
    } catch (e) {
        downloadReportDirect(encodedText);
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
// Cmd+K shortcut to focus input
document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const input = document.getElementById('user-input');
        if (input) input.focus();
    }
});

// Explicitly bind file input change listener for robust Safari compatibility
document.addEventListener("DOMContentLoaded", () => {
    const fileInput = document.getElementById("file-upload");
    if (fileInput) {
        fileInput.addEventListener("change", (e) => {
            if (e.target && e.target.files && e.target.files.length > 0) {
                handleFileUpload(e.target.files);
            }
        });
    }
});

// ==========================================
// AUTHENTICATION
// ==========================================
async function logout() {
    // Navigate directly (not via fetch) so the browser follows the identity provider
    // logout redirect natively without triggering CORS restrictions.
    window.location.href = `${API_URL}/auth/logout`;
}


