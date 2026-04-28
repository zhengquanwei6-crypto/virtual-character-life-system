import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  ImageIcon,
  Loader2,
  MessageCircle,
  MonitorSmartphone,
  RefreshCw,
  Save,
  Send,
  Settings2,
  Sparkles,
  TestTube2,
  Wand2,
  Workflow,
  XCircle
} from "lucide-react";
import "./styles.css";
import {
  AdminApi,
  ApiError,
  CharacterBundle,
  ChatApi,
  ChatMessage,
  GenerationPreset,
  ImageTask,
  LLMConfig,
  NodeMapping,
  WorkflowAnalysis,
  WorkflowTemplate
} from "./api";

type Page = "chat" | "admin";
type AdminTab = "overview" | "character" | "image" | "workflow" | "model" | "test";

const imagePollInterval = 1800;
const imageTimeout = 10 * 60 * 1000;

function isAdminPath() {
  return window.location.pathname.includes("admin");
}

function App() {
  const [page, setPage] = useState<Page>(isAdminPath() ? "admin" : "chat");

  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  useEffect(() => {
    const target = page === "admin" ? "/admin.html" : "/index.html";
    if (window.location.pathname !== target) {
      window.history.replaceState(null, "", target);
    }
  }, [page]);

  return (
    <div className="app">
      <TopNav page={page} setPage={setPage} />
      {page === "chat" ? <ChatPage /> : <AdminPage />}
    </div>
  );
}

function TopNav({ page, setPage }: { page: Page; setPage: (page: Page) => void }) {
  return (
    <nav className="topbar">
      <button className="brand" onClick={() => setPage("chat")}>
        <Sparkles size={20} />
        <span>虚拟角色生命系统</span>
      </button>
      <div className="top-actions">
        <button className={page === "chat" ? "nav-pill active" : "nav-pill"} onClick={() => setPage("chat")}>
          <MessageCircle size={16} />
          用户聊天
        </button>
        <button className={page === "admin" ? "nav-pill active" : "nav-pill"} onClick={() => setPage("admin")}>
          <Settings2 size={16} />
          管理后台
        </button>
      </div>
    </nav>
  );
}

function ChatPage() {
  const [bundle, setBundle] = useState<CharacterBundle | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("连接中");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let alive = true;
    async function boot() {
      try {
        const character = await ChatApi.getDefaultCharacter();
        if (!alive) return;
        setBundle(character);
        const session = await ChatApi.createSession(character.character?.id);
        if (!alive) return;
        setSessionId(session.id);
        setStatus("在线");
      } catch (err) {
        setStatus("离线");
        setError(errorText(err));
      }
    }
    boot();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function pollTask(taskId: string, startedAt = Date.now()) {
    if (Date.now() - startedAt > imageTimeout) {
      updateTask(taskId, { status: "failed", errorCode: "IMAGE_TASK_TIMEOUT", errorMessage: "图片生成超时" });
      return;
    }
    try {
      const task = await ChatApi.getImageTask(taskId);
      updateTask(taskId, task);
      if (["queued", "running", "submitted"].includes(task.status)) {
        window.setTimeout(() => pollTask(taskId, startedAt), imagePollInterval);
      }
    } catch (err) {
      updateTask(taskId, { status: "failed", errorMessage: errorText(err) });
    }
  }

  function updateTask(taskId: string, next: Partial<ImageTask>) {
    setMessages((items) =>
      items.map((message) => ({
        ...message,
        imageTasks: (message.imageTasks || []).map((task) => (task.id === taskId ? { ...task, ...next } : task))
      }))
    );
  }

  async function submit() {
    const text = content.trim();
    if (!text || !sessionId || sending) return;
    setContent("");
    setSending(true);
    setStatus("思考中");
    setError("");
    try {
      const result = await ChatApi.sendMessage(sessionId, text);
      const assistant = { ...result.assistantMessage, imageTasks: result.imageTasks || [] };
      setMessages((items) => [...items, result.userMessage, assistant]);
      setStatus("在线");
      (result.imageTasks || []).forEach((task) => window.setTimeout(() => pollTask(task.id), 500));
    } catch (err) {
      setStatus("在线");
      setMessages((items) => [
        ...items,
        {
          id: `local_${Date.now()}`,
          role: "assistant",
          content: `发送失败：${errorText(err)}`,
          imageTaskIds: [],
          imageTasks: []
        }
      ]);
    } finally {
      setSending(false);
    }
  }

  const profile = bundle?.profile;
  const avatar = profile?.avatarUrl;

  return (
    <main className="chat-layout">
      <aside className="character-stage">
        <div className="stage-card">
          <div className="portrait">
            {avatar ? <img src={avatar} alt="角色头像" /> : <span>{(profile?.name || "AI").slice(0, 2)}</span>}
          </div>
          <div>
            <p className="eyebrow">生命核心</p>
            <h1>{profile?.name || "默认角色"}</h1>
            <p>{profile?.description || "正在加载角色设定与视觉记忆。"}</p>
          </div>
          <div className="metric-grid">
            <Metric label="LLM" value={status === "离线" ? "异常" : "待命"} />
            <Metric label="ComfyUI" value="异步生图" />
            <Metric label="图片" value="持久化" />
            <Metric label="端" value="Web / APK" />
          </div>
        </div>
      </aside>

      <section className="chat-card">
        <header className="chat-header">
          <div className="small-avatar">{avatar ? <img src={avatar} alt="角色头像" /> : <Bot size={22} />}</div>
          <div>
            <h2>{profile?.name || "连接角色中"}</h2>
            <p>{profile?.description || "你可以直接聊天，也可以让角色生成照片或画面。"}</p>
          </div>
          <StatusBadge ok={status !== "离线"} text={status} />
        </header>

        <div className="message-list" ref={listRef}>
          {messages.length === 0 ? (
            <div className="empty-state">
              <Sparkles size={28} />
              <strong>开始一次真实图文对话</strong>
              <span>试试：“给我看看你的样子”或 “please generate a photo”。</span>
              {error ? <em>{error}</em> : null}
            </div>
          ) : (
            messages.map((message) => <MessageBubble key={message.id} message={message} onRetry={pollTask} />)
          )}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <textarea
            value={content}
            onChange={(event) => setContent(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                submit();
              }
            }}
            disabled={!sessionId || sending}
            placeholder="输入消息，例如：给我看看你的样子"
            rows={1}
          />
          <button className="primary icon-button" disabled={!content.trim() || !sessionId || sending}>
            {sending ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
            发送
          </button>
        </form>
      </section>
    </main>
  );
}

function MessageBubble({ message, onRetry }: { message: ChatMessage; onRetry: (taskId: string) => void }) {
  const user = message.role === "user";
  return (
    <article className={user ? "message user" : "message assistant"}>
      <div className="bubble">
        <p>{message.content}</p>
        {(message.imageTasks || []).map((task) => (
          <ImageTaskView key={task.id} task={task} onRetry={onRetry} />
        ))}
      </div>
    </article>
  );
}

function ImageTaskView({ task, onRetry }: { task: ImageTask; onRetry: (taskId: string) => void }) {
  if (task.status === "succeeded" && task.generatedAsset?.publicUrl) {
    return (
      <figure className="generated-image">
        <img src={task.generatedAsset.publicUrl} alt="生成图片" />
        <figcaption>生成完成</figcaption>
      </figure>
    );
  }
  if (task.status === "failed") {
    return (
      <div className="task-box failed">
        <XCircle size={18} />
        <span>{friendlyImageError(task)}</span>
        <button type="button" onClick={() => onRetry(task.id)}>
          重新查询
        </button>
      </div>
    );
  }
  return (
    <div className="task-box">
      <Loader2 className="spin" size={18} />
      <span>{task.status === "queued" ? "图片已排队，正在提交" : "图片生成中，请稍候"}</span>
    </div>
  );
}

function AdminPage() {
  const [tab, setTab] = useState<AdminTab>("overview");
  const [healthTick, setHealthTick] = useState(0);
  const tabs: { id: AdminTab; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "概览", icon: <MonitorSmartphone size={17} /> },
    { id: "character", label: "角色配置", icon: <Bot size={17} /> },
    { id: "image", label: "生图配置", icon: <ImageIcon size={17} /> },
    { id: "workflow", label: "工作流", icon: <Workflow size={17} /> },
    { id: "model", label: "模型连接", icon: <Settings2 size={17} /> },
    { id: "test", label: "测试中心", icon: <TestTube2 size={17} /> }
  ];

  return (
    <main className="admin-layout">
      <aside className="admin-nav">
        <div>
          <p className="eyebrow">管理后台</p>
          <h1>配置中心</h1>
          <span>常用项优先，高级项收纳。</span>
        </div>
        {tabs.map((item) => (
          <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>
            {item.icon}
            {item.label}
            <ChevronRight size={15} />
          </button>
        ))}
      </aside>
      <section className="admin-main">
        {tab === "overview" && <OverviewPanel key={healthTick} refresh={() => setHealthTick((value) => value + 1)} />}
        {tab === "character" && <CharacterPanel />}
        {tab === "image" && <ImageConfigPanel />}
        {tab === "workflow" && <WorkflowPanel />}
        {tab === "model" && <ModelPanel refreshHealth={() => setHealthTick((value) => value + 1)} />}
        {tab === "test" && <TestPanel />}
      </section>
    </main>
  );
}

function OverviewPanel({ refresh }: { refresh: () => void }) {
  const [llm, setLlm] = useState<any>(null);
  const [comfy, setComfy] = useState<any>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.allSettled([AdminApi.llmHealth(), AdminApi.comfyuiHealth()])
      .then(([llmResult, comfyResult]) => {
        if (llmResult.status === "fulfilled") setLlm(llmResult.value);
        if (comfyResult.status === "fulfilled") setComfy(comfyResult.value);
        if (llmResult.status === "rejected" || comfyResult.status === "rejected") setError("部分服务不可用，请检查配置。");
      })
      .catch((err) => setError(errorText(err)));
  }, []);

  return (
    <Panel title="运行概览" kicker="Dashboard" action={<button onClick={refresh}><RefreshCw size={16} />刷新</button>}>
      <div className="summary-grid">
        <SummaryCard title="LLM 连接" value={llm?.enabled ? "真实接口" : "Mock 模式"} ok={Boolean(llm?.ok)} detail={llm?.baseUrl || "未配置"} />
        <SummaryCard title="ComfyUI" value={comfy?.enabled ? "真实接口" : "Mock 模式"} ok={Boolean(comfy?.ok)} detail={comfy?.baseUrl || "未配置"} />
        <SummaryCard title="前端体验" value="React 响应式" ok detail="Web / PC / Android WebView 共用一套 UI" />
        <SummaryCard title="配置方式" value="常用优先" ok detail="复杂字段统一放入高级设置" />
      </div>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <div className="guide-list">
        <Step title="1. 先配置模型连接" text="填入 OpenAI-compatible baseUrl、模型与 API Key，拉取模型并测试。" />
        <Step title="2. 再配置角色" text="只需维护名称、头像、简介、基础提示词和生图预设。" />
        <Step title="3. 最后测试链路" text="用测试中心验证聊天、角色卡生成和生图任务。" />
      </div>
    </Panel>
  );
}

function CharacterPanel() {
  const [items, setItems] = useState<CharacterBundle[]>([]);
  const [selected, setSelected] = useState<CharacterBundle | null>(null);
  const [seedText, setSeedText] = useState("温柔、聪明、会陪用户聊天的虚拟角色");
  const [result, setResult] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    const data = await AdminApi.listCharacters();
    setItems(data);
    setSelected(data[0] || null);
  }

  function patch(path: string, value: any) {
    if (!selected) return;
    const next = structuredClone(selected);
    const parts = path.split(".");
    let cursor: any = next;
    parts.slice(0, -1).forEach((part) => (cursor = cursor[part]));
    cursor[parts[parts.length - 1]] = value;
    setSelected(next);
  }

  async function save() {
    if (!selected) return;
    setSaving(true);
    try {
      const payload = {
        code: selected.character.code,
        profile: selected.profile,
        prompt: selected.prompt,
        visual: selected.visual
      };
      const saved = await AdminApi.updateCharacter(selected.character.id, payload);
      setResult(JSON.stringify(saved, null, 2));
      await load();
    } catch (err) {
      setResult(errorText(err));
    } finally {
      setSaving(false);
    }
  }

  async function generateCard() {
    try {
      const draft = await AdminApi.generateCard(seedText);
      setResult(JSON.stringify(draft, null, 2));
      if (selected) {
        setSelected({
          ...selected,
          profile: { ...selected.profile, ...draft.profile },
          prompt: { ...selected.prompt, ...draft.prompt },
          visual: { ...selected.visual, ...draft.visual }
        });
      }
    } catch (err) {
      setResult(errorText(err));
    }
  }

  if (!selected) {
    return <Panel title="角色配置" kicker="Character"><LoadingState text="正在加载角色" /></Panel>;
  }

  return (
    <Panel title="角色配置" kicker="Character" action={<button onClick={load}><RefreshCw size={16} />刷新</button>}>
      <div className="form-grid two">
        <label>
          <span>选择角色</span>
          <select
            value={selected.character.id}
            onChange={(event) => setSelected(items.find((item) => item.character.id === event.target.value) || null)}
          >
            {items.map((item) => (
              <option key={item.character.id} value={item.character.id}>
                {item.profile.name} {item.character.isDefault ? "（默认）" : ""}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>绑定生图预设 ID</span>
          <input value={selected.visual.generationPresetId || ""} onChange={(e) => patch("visual.generationPresetId", e.target.value)} />
        </label>
        <label>
          <span>角色名称</span>
          <input value={selected.profile.name || ""} onChange={(e) => patch("profile.name", e.target.value)} />
        </label>
        <label>
          <span>头像 URL</span>
          <input value={selected.profile.avatarUrl || ""} onChange={(e) => patch("profile.avatarUrl", e.target.value)} />
        </label>
      </div>
      <label>
        <span>简介</span>
        <textarea value={selected.profile.description || ""} onChange={(e) => patch("profile.description", e.target.value)} />
      </label>
      <label>
        <span>基础角色提示词</span>
        <textarea value={selected.prompt.roleplayPrompt || ""} onChange={(e) => patch("prompt.roleplayPrompt", e.target.value)} />
      </label>
      <label>
        <span>视觉提示词</span>
        <textarea value={selected.visual.visualPrompt || ""} onChange={(e) => patch("visual.visualPrompt", e.target.value)} />
      </label>

      <details className="advanced">
        <summary>高级设置：系统提示词、安全提示词、角色卡草稿</summary>
        <label>
          <span>systemPrompt</span>
          <textarea value={selected.prompt.systemPrompt || ""} onChange={(e) => patch("prompt.systemPrompt", e.target.value)} />
        </label>
        <label>
          <span>safetyPrompt</span>
          <textarea value={selected.prompt.safetyPrompt || ""} onChange={(e) => patch("prompt.safetyPrompt", e.target.value)} />
        </label>
        <div className="form-grid two">
          <label>
            <span>角色卡灵感</span>
            <textarea value={seedText} onChange={(e) => setSeedText(e.target.value)} />
          </label>
          <div className="stack">
            <span className="field-title">LLM 生成角色卡</span>
            <button onClick={generateCard}><Wand2 size={16} />生成并填入草稿</button>
          </div>
        </div>
      </details>

      <div className="button-row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
          保存角色
        </button>
        <button onClick={() => AdminApi.publishCharacter(selected.character.id).then((data) => setResult(JSON.stringify(data, null, 2)))}>
          发布角色
        </button>
      </div>
      <ResultBox value={result} />
    </Panel>
  );
}

function ImageConfigPanel() {
  const [presets, setPresets] = useState<GenerationPreset[]>([]);
  const [preset, setPreset] = useState<GenerationPreset | null>(null);
  const [result, setResult] = useState("");

  useEffect(() => {
    load();
  }, []);

  async function load() {
    const data = await AdminApi.listGenerationPresets();
    setPresets(data);
    setPreset(data[0] || null);
  }

  function update(key: keyof GenerationPreset, value: any) {
    if (!preset) return;
    setPreset({ ...preset, [key]: value });
  }

  async function save() {
    if (!preset) return;
    try {
      const payload = {
        name: preset.name,
        description: preset.description,
        workflowTemplateId: preset.workflowTemplateId,
        checkpoint: preset.checkpoint,
        loras: preset.loras || [],
        width: Number(preset.width),
        height: Number(preset.height),
        steps: Number(preset.steps),
        cfg: Number(preset.cfg),
        sampler: preset.sampler,
        scheduler: preset.scheduler,
        seedMode: preset.seedMode,
        seed: preset.seed,
        positivePromptPrefix: preset.positivePromptPrefix,
        positivePromptSuffix: preset.positivePromptSuffix,
        negativePrompt: preset.negativePrompt
      };
      const data = await AdminApi.updateGenerationPreset(preset.id, payload);
      setResult(JSON.stringify(data, null, 2));
      await load();
    } catch (err) {
      setResult(errorText(err));
    }
  }

  if (!preset) return <Panel title="生图配置" kicker="Generation"><LoadingState text="正在加载生图预设" /></Panel>;

  return (
    <Panel title="生图配置" kicker="Generation Preset" action={<button onClick={load}><RefreshCw size={16} />刷新</button>}>
      <label>
        <span>选择预设</span>
        <select value={preset.id} onChange={(e) => setPreset(presets.find((item) => item.id === e.target.value) || null)}>
          {presets.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
      </label>
      <div className="form-grid two">
        <label><span>预设名称</span><input value={preset.name || ""} onChange={(e) => update("name", e.target.value)} /></label>
        <label><span>Checkpoint</span><input value={preset.checkpoint || ""} onChange={(e) => update("checkpoint", e.target.value)} /></label>
        <label><span>宽度</span><input type="number" value={preset.width || 768} onChange={(e) => update("width", Number(e.target.value))} /></label>
        <label><span>高度</span><input type="number" value={preset.height || 1024} onChange={(e) => update("height", Number(e.target.value))} /></label>
        <label><span>步数</span><input type="number" value={preset.steps || 24} onChange={(e) => update("steps", Number(e.target.value))} /></label>
        <label><span>CFG</span><input type="number" step="0.1" value={preset.cfg || 7} onChange={(e) => update("cfg", Number(e.target.value))} /></label>
      </div>
      <label><span>反向提示词</span><textarea value={preset.negativePrompt || ""} onChange={(e) => update("negativePrompt", e.target.value)} /></label>
      <details className="advanced">
        <summary>高级设置：LoRA、采样器、Seed、提示词前后缀</summary>
        <div className="form-grid two">
          <label><span>Sampler</span><input value={preset.sampler || ""} onChange={(e) => update("sampler", e.target.value)} /></label>
          <label><span>Scheduler</span><input value={preset.scheduler || ""} onChange={(e) => update("scheduler", e.target.value)} /></label>
          <label><span>Seed 模式</span><input value={preset.seedMode || "random"} onChange={(e) => update("seedMode", e.target.value)} /></label>
          <label><span>WorkflowTemplate ID</span><input value={preset.workflowTemplateId || ""} onChange={(e) => update("workflowTemplateId", e.target.value)} /></label>
        </div>
        <JsonTextarea label="LoRA 列表 JSON" value={preset.loras || []} onChange={(value) => update("loras", value)} />
        <label><span>正向提示词前缀</span><textarea value={preset.positivePromptPrefix || ""} onChange={(e) => update("positivePromptPrefix", e.target.value)} /></label>
        <label><span>正向提示词后缀</span><textarea value={preset.positivePromptSuffix || ""} onChange={(e) => update("positivePromptSuffix", e.target.value)} /></label>
      </details>
      <div className="button-row"><button className="primary" onClick={save}><Save size={16} />保存预设</button></div>
      <ResultBox value={result} />
    </Panel>
  );
}

function WorkflowPanel() {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [mappings, setMappings] = useState<NodeMapping[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowTemplate | null>(null);
  const [mapping, setMapping] = useState<NodeMapping | null>(null);
  const [analysis, setAnalysis] = useState<WorkflowAnalysis | null>(null);
  const [result, setResult] = useState("");

  useEffect(() => {
    load();
  }, []);

  async function load() {
    const [workflowData, mappingData] = await Promise.all([AdminApi.listWorkflowTemplates(), AdminApi.listNodeMappings()]);
    setWorkflows(workflowData);
    setMappings(mappingData);
    setWorkflow(workflowData[0] || null);
    setMapping(mappingData[0] || null);
  }

  async function analyze() {
    if (!workflow) return;
    try {
      const data = await AdminApi.analyzeWorkflow(workflow.workflowJson);
      setAnalysis(data);
      setResult(JSON.stringify(data.guessedMapping, null, 2));
      if (mapping) setMapping({ ...mapping, mappings: data.guessedMapping });
    } catch (err) {
      setResult(errorText(err));
    }
  }

  async function saveAll() {
    try {
      let savedMapping = mapping;
      if (mapping) {
        savedMapping = await AdminApi.updateNodeMapping(mapping.id, {
          name: mapping.name,
          description: mapping.description,
          mappings: mapping.mappings
        });
      }
      if (workflow) {
        const savedWorkflow = await AdminApi.updateWorkflowTemplate(workflow.id, {
          name: workflow.name,
          description: workflow.description,
          workflowJson: workflow.workflowJson,
          nodeMappingId: savedMapping?.id || workflow.nodeMappingId
        });
        setResult(JSON.stringify({ savedWorkflow, savedMapping }, null, 2));
      }
    } catch (err) {
      setResult(errorText(err));
    }
  }

  if (!workflow || !mapping) return <Panel title="工作流配置" kicker="Workflow"><LoadingState text="正在加载 Workflow 与 NodeMapping" /></Panel>;

  return (
    <Panel title="工作流配置" kicker="Workflow Wizard" action={<button onClick={load}><RefreshCw size={16} />刷新</button>}>
      <div className="wizard-steps">
        <Step title="1. 选择 Workflow" text="粘贴 ComfyUI API Format JSON。" />
        <Step title="2. 自动分析" text="后端解析节点并猜测 NodeMapping。" />
        <Step title="3. 保存并校验" text="管理员可手动修正映射。" />
      </div>
      <div className="form-grid two">
        <label>
          <span>Workflow</span>
          <select value={workflow.id} onChange={(e) => setWorkflow(workflows.find((item) => item.id === e.target.value) || null)}>
            {workflows.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
        <label>
          <span>NodeMapping</span>
          <select value={mapping.id} onChange={(e) => setMapping(mappings.find((item) => item.id === e.target.value) || null)}>
            {mappings.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
        </label>
      </div>
      <details className="advanced" open>
        <summary>高级设置：Workflow JSON 与 NodeMapping JSON</summary>
        <JsonTextarea label="workflowJson" value={workflow.workflowJson} onChange={(value) => setWorkflow({ ...workflow, workflowJson: value })} rows={12} />
        <JsonTextarea label="mappings" value={mapping.mappings} onChange={(value) => setMapping({ ...mapping, mappings: value })} rows={10} />
      </details>
      <div className="button-row">
        <button className="primary" onClick={analyze}><Wand2 size={16} />分析 Workflow</button>
        <button onClick={saveAll}><Save size={16} />保存配置</button>
        <button onClick={() => AdminApi.validateNodeMapping(mapping.id, { workflowJson: workflow.workflowJson }).then((data) => setResult(JSON.stringify(data, null, 2))).catch((err) => setResult(errorText(err)))}>
          校验 NodeMapping
        </button>
      </div>
      {analysis ? (
        <div className="node-grid">
          {analysis.nodes.slice(0, 12).map((node) => (
            <div className="node-card" key={node.nodeId}>
              <strong>{node.nodeId}</strong>
              <span>{node.classType}</span>
              <code>{Object.keys(node.inputs || {}).join(", ") || "无 inputs"}</code>
            </div>
          ))}
        </div>
      ) : null}
      <ResultBox value={result} />
    </Panel>
  );
}

function ModelPanel({ refreshHealth }: { refreshHealth: () => void }) {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    AdminApi.getLlmConfig().then(setConfig).catch((err) => setResult(errorText(err)));
  }, []);

  if (!config) return <Panel title="模型连接" kicker="LLM"><LoadingState text="正在读取模型配置" /></Panel>;

  async function save() {
    const currentConfig = config;
    if (!currentConfig) return;
    try {
      const data = await AdminApi.saveLlmConfig({ ...currentConfig, apiKey: apiKey || undefined });
      setConfig(data);
      setApiKey("");
      refreshHealth();
      setResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setResult(errorText(err));
    }
  }

  return (
    <Panel title="模型连接" kicker="OpenAI-compatible" action={<StatusBadge ok={config.enabled} text={config.enabled ? "已启用" : "Mock 模式"} />}>
      <Alert>
        后台支持自定义 OpenAI-compatible 接口。ChatGPT Plus/Codex 额度用于 Codex 开发工具，不作为本应用生产聊天 API 额度。
      </Alert>
      <div className="form-grid two">
        <label className="toggle-line">
          <input type="checkbox" checked={config.enabled} onChange={(e) => setConfig({ ...config, enabled: e.target.checked })} />
          <span>启用真实 LLM</span>
        </label>
        <label><span>超时秒数</span><input type="number" value={config.timeout || 60} onChange={(e) => setConfig({ ...config, timeout: Number(e.target.value) })} /></label>
        <label><span>Base URL</span><input value={config.baseUrl || ""} placeholder="https://example.com/v1" onChange={(e) => setConfig({ ...config, baseUrl: e.target.value })} /></label>
        <label><span>模型 ID</span><input value={config.model || ""} placeholder="留空则自动取第一个模型" onChange={(e) => setConfig({ ...config, model: e.target.value })} /></label>
        <label><span>API Key</span><input type="password" value={apiKey} placeholder={config.hasApiKey ? `已配置：${config.maskedApiKey}` : "可留空"} onChange={(e) => setApiKey(e.target.value)} /></label>
      </div>
      <div className="button-row">
        <button className="primary" onClick={save}><Save size={16} />保存模型配置</button>
        <button onClick={() => AdminApi.listLlmModels().then((data) => setResult(JSON.stringify(data, null, 2))).catch((err) => setResult(errorText(err)))}>
          拉取模型
        </button>
        <button onClick={() => AdminApi.testLlm("请用一句话确认模型连接正常").then((data) => setResult(JSON.stringify(data, null, 2))).catch((err) => setResult(errorText(err)))}>
          测试连接
        </button>
      </div>
      <ResultBox value={result} />
    </Panel>
  );
}

function TestPanel() {
  const [characters, setCharacters] = useState<CharacterBundle[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [chatText, setChatText] = useState("请生成一个适合角色的开场白");
  const [imageText, setImageText] = useState("portrait of the default character");
  const [result, setResult] = useState("");
  const [imageUrl, setImageUrl] = useState("");

  useEffect(() => {
    AdminApi.listCharacters().then((data) => {
      setCharacters(data);
      setCharacterId(data[0]?.character.id || "");
    });
  }, []);

  async function testImage() {
    try {
      setImageUrl("");
      const task = await AdminApi.testImage(characterId, imageText);
      setResult(JSON.stringify(task, null, 2));
      const finalTask = await waitForTask(task.id);
      setResult(JSON.stringify(finalTask, null, 2));
      if (finalTask.generatedAsset?.publicUrl) setImageUrl(finalTask.generatedAsset.publicUrl);
    } catch (err) {
      setResult(errorText(err));
    }
  }

  return (
    <Panel title="测试中心" kicker="Test Center">
      <label>
        <span>测试角色</span>
        <select value={characterId} onChange={(e) => setCharacterId(e.target.value)}>
          {characters.map((item) => <option key={item.character.id} value={item.character.id}>{item.profile.name}</option>)}
        </select>
      </label>
      <div className="form-grid two">
        <label><span>测试聊天 / 角色定义</span><textarea value={chatText} onChange={(e) => setChatText(e.target.value)} /></label>
        <label><span>测试画面描述</span><textarea value={imageText} onChange={(e) => setImageText(e.target.value)} /></label>
      </div>
      <div className="button-row">
        <button className="primary" onClick={() => AdminApi.testChat(characterId, chatText).then((data) => setResult(JSON.stringify(data, null, 2))).catch((err) => setResult(errorText(err)))}>
          测试聊天
        </button>
        <button onClick={testImage}>测试生图</button>
      </div>
      {imageUrl ? <img className="preview-image" src={imageUrl} alt="测试生成结果" /> : null}
      <ResultBox value={result} />
    </Panel>
  );
}

async function waitForTask(taskId: string) {
  for (let index = 0; index < 120; index += 1) {
    const task = await ChatApi.getImageTask(taskId);
    if (["succeeded", "failed"].includes(task.status)) return task;
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
  }
  throw new Error("图片任务等待超时");
}

function Panel({ title, kicker, action, children }: { title: string; kicker: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <p className="eyebrow">{kicker}</p>
          <h2>{title}</h2>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

function SummaryCard({ title, value, detail, ok }: { title: string; value: string; detail: string; ok: boolean }) {
  return (
    <div className="summary-card">
      {ok ? <CheckCircle2 className="ok" size={20} /> : <XCircle className="bad" size={20} />}
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}

function StatusBadge({ ok, text }: { ok: boolean; text: string }) {
  return <span className={ok ? "status ok" : "status bad"}>{text}</span>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div><span>{label}</span><strong>{value}</strong></div>;
}

function Step({ title, text }: { title: string; text: string }) {
  return <div className="step"><strong>{title}</strong><span>{text}</span></div>;
}

function Alert({ children, tone = "info" }: { children: React.ReactNode; tone?: "info" | "error" }) {
  return <div className={`alert ${tone}`}>{children}</div>;
}

function LoadingState({ text }: { text: string }) {
  return <div className="loading-state"><Loader2 className="spin" />{text}</div>;
}

function ResultBox({ value }: { value: string }) {
  return value ? <pre className="result-box">{value}</pre> : null;
}

function JsonTextarea({ label, value, onChange, rows = 6 }: { label: string; value: any; onChange: (value: any) => void; rows?: number }) {
  const [raw, setRaw] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [error, setError] = useState("");

  useEffect(() => {
    setRaw(JSON.stringify(value ?? {}, null, 2));
  }, [value]);

  return (
    <label>
      <span>{label}</span>
      <textarea
        rows={rows}
        value={raw}
        onChange={(event) => {
          setRaw(event.target.value);
          try {
            onChange(JSON.parse(event.target.value));
            setError("");
          } catch {
            setError("JSON 格式暂未合法，修正后会自动应用。");
          }
        }}
      />
      {error ? <em className="field-error">{error}</em> : null}
    </label>
  );
}

function errorText(err: unknown) {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return String(err);
}

function friendlyImageError(task: ImageTask) {
  if (task.errorCode === "IMAGE_TASK_TIMEOUT") return "图片生成超时，请稍后重试。";
  if (task.errorCode === "COMFYUI_TIMEOUT") return "ComfyUI 响应超时。";
  if (task.errorCode === "COMFYUI_UNAVAILABLE") return "ComfyUI 暂时不可用。";
  if (task.errorCode === "WORKFLOW_INJECTION_FAILED") return "Workflow 参数注入失败，请检查 NodeMapping。";
  return task.errorMessage || "图片生成失败，请检查生图预设和 ComfyUI 连接。";
}

createRoot(document.getElementById("root")!).render(<App />);
