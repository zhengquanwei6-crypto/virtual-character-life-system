(function () {
  const state = {
    character: null,
    profile: null,
    sessionId: null,
    messages: [],
    sending: false,
  };

  const IMAGE_POLL_INTERVAL_MS = 1800;
  const IMAGE_POLL_TIMEOUT_MS = 10 * 60 * 1000;

  const els = {
    avatar: document.getElementById("characterAvatar"),
    avatarFallback: document.getElementById("avatarFallback"),
    characterName: document.getElementById("characterName"),
    characterDescription: document.getElementById("characterDescription"),
    connectionStatus: document.getElementById("connectionStatus"),
    messageList: document.getElementById("messageList"),
    form: document.getElementById("messageForm"),
    input: document.getElementById("messageInput"),
    sendButton: document.getElementById("sendButton"),
    stageAvatar: document.getElementById("stageAvatar"),
    stageName: document.getElementById("stageName"),
    stageDescription: document.getElementById("stageDescription"),
  };

  function setStatus(text, tone = "neutral") {
    els.connectionStatus.textContent = text;
    els.connectionStatus.dataset.tone = tone;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function normalizeMessage(message) {
    return {
      id: message.id,
      sessionId: message.sessionId,
      role: message.role,
      content: message.content,
      imageTaskIds: message.imageTaskIds || [],
      llmDecision: message.llmDecision || null,
      createdAt: message.createdAt,
      imageTasks: (message.imageTasks || []).map(normalizeImageTask),
    };
  }

  function normalizeImageTask(task) {
    return {
      id: task.id,
      status: task.status || "queued",
      prompt: task.prompt || "",
      negativePrompt: task.negativePrompt || "",
      errorCode: task.errorCode || null,
      errorMessage: task.errorMessage || null,
      generatedAsset: task.generatedAsset || null,
      createdAt: task.createdAt || new Date().toISOString(),
      updatedAt: task.updatedAt || task.createdAt || new Date().toISOString(),
    };
  }

  function renderCharacter() {
    const profile = state.profile || {};
    els.characterName.textContent = profile.name || "Default Character";
    els.characterDescription.textContent = profile.description || "\u7528\u6237\u7aef\u804a\u5929 MVP";
    if (els.stageName) els.stageName.textContent = profile.name || "Default Character";
    if (els.stageDescription) els.stageDescription.textContent = profile.description || "\u89d2\u8272\u72b6\u6001\u5df2\u540c\u6b65";
    els.avatarFallback.textContent = (profile.name || "AI").slice(0, 2).toUpperCase();

    if (profile.avatarUrl) {
      els.avatar.src = profile.avatarUrl;
      els.avatar.style.display = "block";
      els.avatarFallback.style.display = "none";
      if (els.stageAvatar) {
        els.stageAvatar.src = profile.avatarUrl;
        els.stageAvatar.style.display = "block";
      }
    } else {
      els.avatar.removeAttribute("src");
      els.avatar.style.display = "none";
      els.avatarFallback.style.display = "grid";
      if (els.stageAvatar) els.stageAvatar.style.display = "none";
    }
  }

  function imageTaskHtml(task) {
    if (task.status === "succeeded" && task.generatedAsset?.publicUrl) {
      return `
        <figure class="image-result">
          <img src="${escapeHtml(task.generatedAsset.publicUrl)}" alt="\u751f\u6210\u56fe\u7247" />
        </figure>
      `;
    }

    if (task.status === "failed") {
      const reason = friendlyImageError(task);
      return `<div class="image-task failed">\u56fe\u7247\u751f\u6210\u5931\u8d25\uff1a${escapeHtml(reason)}</div>`;
    }

    const label = task.status === "queued" ? "\u56fe\u7247\u5df2\u6392\u961f\uff0c\u6b63\u5728\u63d0\u4ea4" : "\u56fe\u7247\u751f\u6210\u4e2d";
    return `<div class="image-task loading">${label}</div>`;
  }

  function friendlyImageError(task) {
    const code = task.errorCode || "";
    if (code === "IMAGE_TASK_TIMEOUT") return "\u751f\u6210\u8d85\u65f6\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5";
    if (code === "COMFYUI_TIMEOUT") return "ComfyUI \u54cd\u5e94\u8d85\u65f6";
    if (code === "COMFYUI_UNAVAILABLE") return "ComfyUI \u6682\u65f6\u4e0d\u53ef\u7528";
    if (code === "COMFYUI_EXECUTION_FAILED") return "ComfyUI \u6267\u884c\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 Workflow \u548c\u6a21\u578b\u914d\u7f6e";
    if (code === "WORKFLOW_INJECTION_FAILED") return "Workflow \u53c2\u6570\u6ce8\u5165\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5 NodeMapping";
    return task.errorMessage || "\u8bf7\u68c0\u67e5\u751f\u56fe\u9884\u8bbe\u548c ComfyUI \u8fde\u63a5";
  }

  function friendlyChatError(error) {
    const message = error.message || "";
    if (message.includes("LLM request timed out")) return "LLM \u54cd\u5e94\u8d85\u65f6\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5";
    if (message.includes("LLM service is unavailable")) return "LLM \u6682\u65f6\u4e0d\u53ef\u7528";
    if (message.includes("\u8bf7\u6c42\u8d85\u65f6")) return message;
    return message;
  }

  function renderMessages() {
    if (state.messages.length === 0) {
      els.messageList.innerHTML = `
        <div class="empty-state">
          <strong>\u5f00\u59cb\u804a\u5929</strong>
          <span>\u53d1\u9001\u4e00\u53e5\u8bdd\uff0c\u8bd5\u8bd5\u201cplease generate a photo\u201d\u6216\u201c\u7ed9\u6211\u770b\u770b\u4f60\u7684\u6837\u5b50\u201d\u3002</span>
        </div>
      `;
      return;
    }

    els.messageList.innerHTML = state.messages
      .map((message) => {
        const isUser = message.role === "user";
        const taskMarkup = (message.imageTasks || []).map(imageTaskHtml).join("");
        return `
          <article class="message-row ${isUser ? "is-user" : "is-assistant"}">
            <div class="message-bubble">
              <p>${escapeHtml(message.content)}</p>
              ${taskMarkup}
            </div>
          </article>
        `;
      })
      .join("");

    els.messageList.scrollTop = els.messageList.scrollHeight;
  }

  function setSending(value) {
    state.sending = value;
    els.sendButton.disabled = value || !state.sessionId;
    els.input.disabled = !state.sessionId;
    els.sendButton.textContent = value ? "\u53d1\u9001\u4e2d" : "\u53d1\u9001";
  }

  function findMessageByTaskId(taskId) {
    return state.messages.find((message) => (message.imageTasks || []).some((task) => task.id === taskId));
  }

  async function pollImageTask(taskId, startedAt = Date.now()) {
    const owner = findMessageByTaskId(taskId);
    if (!owner) return;

    if (Date.now() - startedAt > IMAGE_POLL_TIMEOUT_MS) {
      owner.imageTasks = owner.imageTasks.map((item) =>
        item.id === taskId
          ? {
              ...item,
              status: "failed",
              errorCode: "IMAGE_TASK_TIMEOUT",
              errorMessage: "\u56fe\u7247\u751f\u6210\u8d85\u65f6",
            }
          : item
      );
      renderMessages();
      return;
    }

    try {
      const task = normalizeImageTask(await window.ChatApi.getImageTask(taskId));
      owner.imageTasks = owner.imageTasks.map((item) => (item.id === taskId ? { ...item, ...task } : item));
      renderMessages();

      if (task.status === "queued" || task.status === "running" || task.status === "submitted") {
        window.setTimeout(() => pollImageTask(taskId, startedAt), IMAGE_POLL_INTERVAL_MS);
      }
    } catch (error) {
      owner.imageTasks = owner.imageTasks.map((item) =>
        item.id === taskId ? { ...item, status: "failed", errorMessage: friendlyChatError(error) } : item
      );
      renderMessages();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    const content = els.input.value.trim();
    if (!content || state.sending || !state.sessionId) return;

    setSending(true);
    setStatus("\u601d\u8003\u4e2d", "neutral");
    els.input.value = "";

    try {
      const result = await window.ChatApi.sendMessage(state.sessionId, content);
      const userMessage = normalizeMessage(result.userMessage);
      const assistantMessage = normalizeMessage(result.assistantMessage);
      assistantMessage.imageTasks = (result.imageTasks || []).map(normalizeImageTask);

      state.messages.push(userMessage, assistantMessage);
      renderMessages();
      setStatus("Online", "ok");

      assistantMessage.imageTasks.forEach((task) => {
        window.setTimeout(() => pollImageTask(task.id), 600);
      });
    } catch (error) {
      setStatus("Online", "ok");
      state.messages.push({
        id: `local_error_${Date.now()}`,
        role: "assistant",
        content: `\u53d1\u9001\u5931\u8d25\uff1a${friendlyChatError(error)}`,
        imageTaskIds: [],
        imageTasks: [],
      });
      renderMessages();
    } finally {
      setSending(false);
      els.input.focus();
    }
  }

  function autoResizeInput() {
    els.input.style.height = "auto";
    els.input.style.height = `${Math.min(140, els.input.scrollHeight)}px`;
  }

  async function init() {
    setStatus("Connecting", "neutral");
    setSending(true);
    renderMessages();

    try {
      const characterData = await window.ChatApi.getDefaultCharacter();
      state.character = characterData.character;
      state.profile = characterData.profile;
      renderCharacter();

      const session = await window.ChatApi.createSession(state.character?.id);
      state.sessionId = session.id;
      setStatus("Online", "ok");
      setSending(false);
      els.input.focus();
    } catch (error) {
      setStatus("Offline", "error");
      els.characterName.textContent = "\u8fde\u63a5\u5931\u8d25";
      els.characterDescription.textContent = error.message;
      setSending(false);
    }
  }

  els.form.addEventListener("submit", handleSubmit);
  els.input.addEventListener("input", autoResizeInput);
  els.input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      els.form.requestSubmit();
    }
  });

  init();
})();
