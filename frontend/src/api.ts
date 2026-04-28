export class ApiError extends Error {
  code?: string;
  details?: unknown;
  status?: number;

  constructor(message: string, code?: string, details?: unknown, status?: number) {
    super(message);
    this.code = code;
    this.details = details;
    this.status = status;
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
  createdAt?: string;
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

export type AdminAIConfig = LLMConfig & {
  temperature?: number;
  purpose?: string;
  notice?: string;
};

export type AITask = {
  id: string;
  type: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  targetType?: string | null;
  targetId?: string | null;
  inputSnapshot?: Record<string, unknown>;
  outputDraft?: Record<string, unknown> | null;
  applyMode?: "draft" | "overwrite" | string;
  appliedAt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  createdAt?: string;
  updatedAt?: string;
};

export type CharacterTemplate = {
  id: string;
  name: string;
  category?: string | null;
  description?: string | null;
  profileDraft: Record<string, unknown>;
  promptDraft: Record<string, unknown>;
  visualDraft: Record<string, unknown>;
  tags?: string[];
  source?: string;
};

export type ComfyResource = {
  resourceType?: string | null;
  items: unknown;
  source?: string;
  fetchedAt?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
};

export type ComfyResourcesResponse = {
  baseUrl?: string;
  enabled?: boolean;
  ok?: boolean;
  mode?: string;
  resources: Record<string, ComfyResource>;
  message?: string;
  errorCode?: string | null;
  errorMessage?: string | null;
  nextStep?: string | null;
};

export type WorkflowTypedAnalysis = WorkflowAnalysis & {
  edges?: Record<string, unknown>[];
  dag?: Record<string, unknown>;
  summary?: Record<string, unknown>;
  typedMapping?: Record<string, unknown>;
  diagnosis?: Record<string, unknown>;
};

export type AdminLoginResult = {
  token: string;
  expiresAt: number;
};

const localFrontend = ["127.0.0.1", "localhost"].includes(window.location.hostname) && window.location.port !== "8000";
export const API_BASE = (window as any).API_BASE || (localFrontend ? "http://127.0.0.1:8000" : "");
const ADMIN_TOKEN_KEY = "vcls_admin_token";

export function getAdminToken() {
  return window.localStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

export function setAdminToken(token: string) {
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
}

type RequestOptions = RequestInit & { timeoutMs?: number; adminAuth?: boolean };

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { timeoutMs = 30000, adminAuth = false, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  const headers: HeadersInit = {
    "Content-Type": "application/json; charset=utf-8",
    ...(fetchOptions.headers || {})
  };

  if (adminAuth) {
    const token = getAdminToken();
    if (token) {
      (headers as Record<string, string>).Authorization = `Bearer ${token}`;
    }
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok || !payload?.success) {
      if (response.status === 401 && adminAuth) {
        clearAdminToken();
      }
      throw new ApiError(
        payload?.error?.message || `请求失败：${response.status}`,
        payload?.error?.code,
        payload?.error?.details,
        response.status
      );
    }
    return payload.data as T;
  } catch (error) {
    if ((error as Error).name === "AbortError") {
      throw new ApiError("请求超时，请检查后端服务、LLM 或 ComfyUI 连接。", "REQUEST_TIMEOUT");
    }
    if (error instanceof SyntaxError) {
      throw new ApiError("后端返回格式异常，请检查服务日志。", "INVALID_RESPONSE");
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
    }),
  version: () => request<{ version: string; llmEnabled: boolean; comfyuiEnabled: boolean }>("/api/system/version")
};

export const AdminApi = {
  login: (password: string) =>
    request<AdminLoginResult>("/api/admin/auth/login", { method: "POST", body: JSON.stringify({ password }) }),
  me: () => request<{ authenticated: boolean }>("/api/admin/auth/me", { adminAuth: true }),
  llmHealth: () => request<any>("/api/admin/system/llm-health", { adminAuth: true }),
  comfyuiHealth: () => request<any>("/api/admin/system/comfyui-health", { adminAuth: true }),
  getLlmConfig: () => request<LLMConfig>("/api/admin/llm-config", { adminAuth: true }),
  saveLlmConfig: (payload: LLMConfig) =>
    request<LLMConfig>("/api/admin/llm-config", { method: "PUT", body: JSON.stringify(payload), adminAuth: true }),
  listLlmModels: () => request<any>("/api/admin/llm-config/models", { timeoutMs: 45000, adminAuth: true }),
  testLlm: (message: string) =>
    request<any>("/api/admin/llm-config/test", {
      method: "POST",
      body: JSON.stringify({ message }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  getAdminAiConfig: () => request<AdminAIConfig>("/api/admin/ai-config", { adminAuth: true }),
  saveAdminAiConfig: (payload: AdminAIConfig) =>
    request<AdminAIConfig>("/api/admin/ai-config", { method: "PUT", body: JSON.stringify(payload), adminAuth: true }),
  listAdminAiModels: () => request<any>("/api/admin/ai-config/models", { timeoutMs: 45000, adminAuth: true }),
  testAdminAi: (message: string) =>
    request<any>("/api/admin/ai-config/test", {
      method: "POST",
      body: JSON.stringify({ message }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  createAiTask: (payload: {
    type: string;
    targetType?: string | null;
    targetId?: string | null;
    inputSnapshot?: Record<string, unknown>;
    applyMode?: "draft" | "overwrite";
  }) =>
    request<AITask>("/api/admin/ai-tasks", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 90000,
      adminAuth: true
    }),
  getAiTask: (taskId: string) =>
    request<AITask>(`/api/admin/ai-tasks/${encodeURIComponent(taskId)}`, { timeoutMs: 45000, adminAuth: true }),
  applyAiTask: (taskId: string, overwrite = false) =>
    request<any>(`/api/admin/ai-tasks/${encodeURIComponent(taskId)}/apply`, {
      method: "POST",
      body: JSON.stringify({ overwrite }),
      adminAuth: true
    }),
  listCharacterTemplates: () => request<CharacterTemplate[]>("/api/admin/character-templates", { adminAuth: true }),
  comfyDiagnostics: () => request<ComfyResourcesResponse>("/api/admin/comfyui/diagnostics", { adminAuth: true }),
  refreshComfyResources: () =>
    request<ComfyResourcesResponse>("/api/admin/comfyui/resources/refresh", {
      method: "POST",
      body: JSON.stringify({ force: true }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  listComfyResources: () => request<ComfyResourcesResponse>("/api/admin/comfyui/resources", { adminAuth: true }),
  getComfyResource: (resourceType: string) =>
    request<ComfyResource>(`/api/admin/comfyui/resources/${encodeURIComponent(resourceType)}`, { adminAuth: true }),
  getComfyObjectInfo: () => request<ComfyResource>("/api/admin/comfyui/object-info", { timeoutMs: 60000, adminAuth: true }),
  getComfyQueue: () => request<ComfyResource>("/api/admin/comfyui/queue", { adminAuth: true }),
  listCharacters: () => request<CharacterBundle[]>("/api/admin/characters", { adminAuth: true }),
  updateCharacter: (id: string, payload: any) =>
    request<CharacterBundle>(`/api/admin/characters/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      adminAuth: true
    }),
  publishCharacter: (id: string) =>
    request<CharacterBundle>(`/api/admin/characters/${encodeURIComponent(id)}/publish`, { method: "POST", adminAuth: true }),
  generateCard: (seedText: string) =>
    request<any>("/api/admin/characters/generate-card", {
      method: "POST",
      body: JSON.stringify({ seedText }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  listGenerationPresets: () => request<GenerationPreset[]>("/api/admin/generation-presets", { adminAuth: true }),
  updateGenerationPreset: (id: string, payload: any) =>
    request<GenerationPreset>(`/api/admin/generation-presets/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      adminAuth: true
    }),
  listWorkflowTemplates: () => request<WorkflowTemplate[]>("/api/admin/workflow-templates", { adminAuth: true }),
  updateWorkflowTemplate: (id: string, payload: any) =>
    request<WorkflowTemplate>(`/api/admin/workflow-templates/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
      adminAuth: true
    }),
  analyzeWorkflow: (workflowJson: Record<string, unknown>) =>
    request<WorkflowAnalysis>("/api/admin/workflow-templates/analyze", {
      method: "POST",
      body: JSON.stringify({ workflowJson }),
      adminAuth: true
    }),
  parseWorkflow: (workflowJson: Record<string, unknown>) =>
    request<WorkflowTypedAnalysis>("/api/admin/workflow-templates/parse", {
      method: "POST",
      body: JSON.stringify({ workflowJson }),
      timeoutMs: 60000,
      adminAuth: true
    }),
  analyzeWorkflowAi: (workflowJson: Record<string, unknown>) =>
    request<AITask>("/api/admin/workflow-templates/analyze-ai", {
      method: "POST",
      body: JSON.stringify({ workflowJson }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  draftWorkflowMapping: (workflowId: string) =>
    request<any>(`/api/admin/workflow-templates/${encodeURIComponent(workflowId)}/mapping-draft`, {
      method: "POST",
      timeoutMs: 60000,
      adminAuth: true
    }),
  diagnoseWorkflow: (workflowId: string) =>
    request<any>(`/api/admin/workflow-templates/${encodeURIComponent(workflowId)}/diagnose`, {
      method: "POST",
      timeoutMs: 60000,
      adminAuth: true
    }),
  listNodeMappings: () => request<NodeMapping[]>("/api/admin/node-mappings", { adminAuth: true }),
  updateNodeMapping: (id: string, payload: any) =>
    request<NodeMapping>(`/api/admin/node-mappings/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
      adminAuth: true
    }),
  validateNodeMapping: (id: string, payload: any) =>
    request<any>(`/api/admin/node-mappings/${encodeURIComponent(id)}/validate`, {
      method: "POST",
      body: JSON.stringify(payload),
      adminAuth: true
    }),
  validateNodeMappingTyped: (id: string, payload: any) =>
    request<any>(`/api/admin/node-mappings/${encodeURIComponent(id)}/validate-typed`, {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
      adminAuth: true
    }),
  testChat: (characterId: string, message: string) =>
    request<any>(`/api/admin/characters/${encodeURIComponent(characterId)}/test-chat`, {
      method: "POST",
      body: JSON.stringify({ message }),
      timeoutMs: 90000,
      adminAuth: true
    }),
  testImage: (characterId: string, imagePrompt: string) =>
    request<ImageTask>(`/api/admin/characters/${encodeURIComponent(characterId)}/test-image`, {
      method: "POST",
      body: JSON.stringify({ imagePrompt }),
      timeoutMs: 45000,
      adminAuth: true
    })
};
