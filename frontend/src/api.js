(function () {
  const API_BASE = window.API_BASE || "http://127.0.0.1:8000";

  async function request(path, options = {}) {
    const { timeoutMs = 20000, ...fetchOptions } = options;
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), timeoutMs);

    try {
      const response = await fetch(`${API_BASE}${path}`, {
        ...fetchOptions,
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json; charset=utf-8",
          ...(fetchOptions.headers || {}),
        },
      });

      const payload = await response.json();
      if (!response.ok || !payload.success) {
        const message = payload.error?.message || `Request failed: ${response.status}`;
        throw new Error(message);
      }
      return payload.data;
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("\u8bf7\u6c42\u8d85\u65f6\uff0c\u8bf7\u68c0\u67e5\u540e\u7aef\u662f\u5426\u6b63\u5e38\u54cd\u5e94");
      }
      throw error;
    } finally {
      window.clearTimeout(timer);
    }
  }

  window.ChatApi = {
    request,

    getDefaultCharacter() {
      return request("/api/user/characters/default");
    },

    createSession(characterId) {
      return request("/api/user/chat-sessions", {
        method: "POST",
        body: JSON.stringify(characterId ? { characterId } : {}),
      });
    },

    sendMessage(sessionId, content) {
      return request(`/api/user/chat-sessions/${encodeURIComponent(sessionId)}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
        timeoutMs: 90000,
      });
    },

    getImageTask(taskId) {
      return request(`/api/user/image-tasks/${encodeURIComponent(taskId)}`, {
        timeoutMs: 45000,
      });
    },
  };

  window.AdminApi = {
    llmHealth() {
      return request("/api/admin/system/llm-health");
    },

    comfyuiHealth() {
      return request("/api/admin/system/comfyui-health");
    },

    listCharacters() {
      return request("/api/admin/characters");
    },

    createCharacter(payload) {
      return request("/api/admin/characters", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    updateCharacter(characterId, payload) {
      return request(`/api/admin/characters/${encodeURIComponent(characterId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },

    publishCharacter(characterId) {
      return request(`/api/admin/characters/${encodeURIComponent(characterId)}/publish`, {
        method: "POST",
      });
    },

    generateCard(seedText) {
      return request("/api/admin/characters/generate-card", {
        method: "POST",
        body: JSON.stringify({ seedText }),
      });
    },

    listGenerationPresets() {
      return request("/api/admin/generation-presets");
    },

    createGenerationPreset(payload) {
      return request("/api/admin/generation-presets", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    updateGenerationPreset(presetId, payload) {
      return request(`/api/admin/generation-presets/${encodeURIComponent(presetId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },

    listWorkflowTemplates() {
      return request("/api/admin/workflow-templates");
    },

    createWorkflowTemplate(payload) {
      return request("/api/admin/workflow-templates", {
        method: "POST",
        body: JSON.stringify(payload),
        timeoutMs: 60000,
      });
    },

    updateWorkflowTemplate(workflowId, payload) {
      return request(`/api/admin/workflow-templates/${encodeURIComponent(workflowId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
        timeoutMs: 60000,
      });
    },

    validateWorkflowTemplate(workflowId) {
      return request(`/api/admin/workflow-templates/${encodeURIComponent(workflowId)}/validate`, {
        method: "POST",
      });
    },

    listNodeMappings() {
      return request("/api/admin/node-mappings");
    },

    createNodeMapping(payload) {
      return request("/api/admin/node-mappings", {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    updateNodeMapping(mappingId, payload) {
      return request(`/api/admin/node-mappings/${encodeURIComponent(mappingId)}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
    },

    validateNodeMapping(mappingId, payload = {}) {
      return request(`/api/admin/node-mappings/${encodeURIComponent(mappingId)}/validate`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },

    testChat(characterId, message) {
      return request(`/api/admin/characters/${encodeURIComponent(characterId)}/test-chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
        timeoutMs: 90000,
      });
    },

    testImage(characterId, imagePrompt) {
      return request(`/api/admin/characters/${encodeURIComponent(characterId)}/test-image`, {
        method: "POST",
        body: JSON.stringify({ imagePrompt }),
        timeoutMs: 45000,
      });
    },
  };
})();
