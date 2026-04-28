export class ApiError extends Error {
  code?: string;
  details?: unknown;

  constructor(message: string, code?: string, details?: unknown) {
    super(message);
    this.code = code;
    this.details = details;
  }
}

export type CharacterBundle = {
  character: {
    id: string;
    code: string;
    status: string;
    version: number;
    isDefault?: boolean;
  };
  profile: {
    name: string;
    avatarUrl?: string | null;
    description?: string | null;
    personality?: string | null;
    scenario?: string | null;
    firstMessage?: string | null;
    tags?: string[];
  };
  prompt: {
    systemPrompt: string;
    roleplayPrompt: string;
    conversationStyle?: string | null;
    safetyPrompt?: string | null;
  };
  visual: {
    visualPrompt: string;
    visualNegativePrompt?: string | null;
    generationPresetId: string;
  };
};

export type GeneratedAsset = {
  id: string;
  publicUrl: string;
  filePath: string;
  width: number;
  height: number;
  fileSize: number;
  format: string;
};

export type ImageTask = {
  id: string;
  status: string;
  prompt?: string;
  negativePrompt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  generatedAsset?: GeneratedAsset | null;
  createdAt?: string;
};

export type ChatMessage = {
  id: string;
  sessionId?: string;
  role: "user" | "assistant" | string;
  content: string;
  imageTaskIds: string[];
  llmDecision?: Record<string, unknown> | null;
  imageTasks?: ImageTask[];
};

export type GenerationPreset = {
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  version?: number;
  workflowTemplateId: string;
  checkpoint: string;
  loras: Record<string, unknown>[];
  width: number;
  height: number;
  steps: number;
  cfg: number;
  sampler: string;
  scheduler?: string | null;
  seedMode: string;
  seed?: number | null;
  positivePromptPrefix?: string | null;
  positivePromptSuffix?: string | null;
  negativePrompt?: string | null;
};

export type WorkflowTemplate = {
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  version?: number;
  workflowJson: Record<string, unknown>;
  nodeMappingId?: string | null;
};

export type NodeMapping = {
  id: string;
  name: string;
  description?: string | null;
  status?: string;
  version?: number;
  mappings: Record<string, unknown>;
};

export type WorkflowAnalysis = {
  analyzedNodes: number;
  nodes: { nodeId: string; classType: string; inputs: Record<string, unknown> }[];
  guessedMapping: Record<string, unknown>;
};

export type LLMConfig = {
  enabled: boolean;
  baseUrl: string;
  model?: string | null;
  timeout: number;
  source?: string;
  hasApiKey?: boolean;
  maskedApiKey?: string | null;
  apiKey?: string;
  codexNotice?: string;
};

const localFrontend = ["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port !== "8000";
const API_BASE = (window as any).API_BASE || (localFrontend ? "http://127.0.0.1:8000" : "");

async function request<T>(path: string, options: RequestInit & { timeoutMs?: number } = {}): Promise<T> {
  const { timeoutMs = 30000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json; charset=utf-8",
        ...(fetchOptions.headers || {})
      }
    });
    const payload = await response.json();
    if (!response.ok || !payload.success) {
      throw new ApiError(payload.error?.message || `请求失败：${response.status}`, payload.error?.code, payload.error?.details);
    }
    return payload.data as T;
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      throw new ApiError("请求超时，请检查后端服务或外部模型连接。", "REQUEST_TIMEOUT");
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export const ChatApi = {
  getDefaultCharacter: () => request<CharacterBundle>("/api/user/characters/default"),
  createSession: (characterId?: string) =>
    request<{ id: string }>("/api/user/chat-sessions", {
      method: "POST",
      body: JSON.stringify(characterId ? { characterId } : {})
    }),
  sendMessage: (sessionId: string, content: string) =>
    request<{ userMessage: ChatMessage; assistantMessage: ChatMessage; imageTasks: ImageTask[] }>(
      `/api/user/chat-sessions/${encodeURIComponent(sessionId)}/messages`,
      {
        method: "POST",
        body: JSON.stringify({ content }),
        timeoutMs: 90000
      }
    ),
  getImageTask: (taskId: string) =>
    request<ImageTask>(`/api/user/image-tasks/${encodeURIComponent(taskId)}`, {
      timeoutMs: 45000
    })
};

export const AdminApi = {
  llmHealth: () => request<any>("/api/admin/system/llm-health"),
  comfyuiHealth: () => request<any>("/api/admin/system/comfyui-health"),
  getLlmConfig: () => request<LLMConfig>("/api/admin/llm-config"),
  saveLlmConfig: (payload: LLMConfig) =>
    request<LLMConfig>("/api/admin/llm-config", { method: "PUT", body: JSON.stringify(payload) }),
  listLlmModels: () => request<any>("/api/admin/llm-config/models", { timeoutMs: 45000 }),
  testLlm: (message: string) =>
    request<any>("/api/admin/llm-config/test", { method: "POST", body: JSON.stringify({ message }), timeoutMs: 90000 }),
  listCharacters: () => request<CharacterBundle[]>("/api/admin/characters"),
  updateCharacter: (id: string, payload: any) =>
    request<CharacterBundle>(`/api/admin/characters/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
  publishCharacter: (id: string) =>
    request<CharacterBundle>(`/api/admin/characters/${encodeURIComponent(id)}/publish`, { method: "POST" }),
  generateCard: (seedText: string) =>
    request<any>("/api/admin/characters/generate-card", { method: "POST", body: JSON.stringify({ seedText }), timeoutMs: 90000 }),
  listGenerationPresets: () => request<GenerationPreset[]>("/api/admin/generation-presets"),
  updateGenerationPreset: (id: string, payload: any) =>
    request<GenerationPreset>(`/api/admin/generation-presets/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload)
    }),
  listWorkflowTemplates: () => request<WorkflowTemplate[]>("/api/admin/workflow-templates"),
  updateWorkflowTemplate: (id: string, payload: any) =>
    request<WorkflowTemplate>(`/api/admin/workflow-templates/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      timeoutMs: 60000
    }),
  analyzeWorkflow: (workflowJson: Record<string, unknown>) =>
    request<WorkflowAnalysis>("/api/admin/workflow-templates/analyze", {
      method: "POST",
      body: JSON.stringify({ workflowJson })
    }),
  listNodeMappings: () => request<NodeMapping[]>("/api/admin/node-mappings"),
  updateNodeMapping: (id: string, payload: any) =>
    request<NodeMapping>(`/api/admin/node-mappings/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) }),
  validateNodeMapping: (id: string, payload: any) =>
    request<any>(`/api/admin/node-mappings/${encodeURIComponent(id)}/validate`, { method: "POST", body: JSON.stringify(payload) }),
  testChat: (characterId: string, message: string) =>
    request<any>(`/api/admin/characters/${encodeURIComponent(characterId)}/test-chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
      timeoutMs: 90000
    }),
  testImage: (characterId: string, imagePrompt: string) =>
    request<ImageTask>(`/api/admin/characters/${encodeURIComponent(characterId)}/test-image`, {
      method: "POST",
      body: JSON.stringify({ imagePrompt }),
      timeoutMs: 45000
    })
};
