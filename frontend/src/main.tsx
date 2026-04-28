import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Bot,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Eye,
  ImageIcon,
  KeyRound,
  Loader2,
  LockKeyhole,
  LogOut,
  MessageCircle,
  MonitorSmartphone,
  RefreshCw,
  RotateCcw,
  Save,
  Send,
  Settings2,
  ShieldCheck,
  Sparkles,
  TestTube2,
  Wand2,
  Workflow,
  X,
  XCircle
} from "lucide-react";
import "./styles.css";
import {
  AdminApi,
  AdminAIConfig,
  AITask,
  API_BASE,
  ApiError,
  CharacterBundle,
  CharacterTemplate,
  ChatApi,
  ChatMessage,
  clearAdminToken,
  ComfyResourcesResponse,
  GenerationPreset,
  getAdminToken,
  ImageTask,
  LLMConfig,
  NodeMapping,
  setAdminToken,
  WorkflowAnalysis,
  WorkflowTypedAnalysis,
  WorkflowTemplate
} from "./api";

type Page = "chat" | "admin";
type AdminTab = "overview" | "ai" | "resources" | "character" | "image" | "workflow" | "model" | "test";
type Toast = { id: number; tone: "success" | "error" | "info"; text: string };

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

  function navigate(next: Page) {
    setPage(next);
    const target = next === "admin" ? "/admin.html" : "/index.html";
    if (window.location.pathname !== target) {
      window.history.replaceState(null, "", target);
    }
  }

  return (
    <div className={`app app-${page}`}>
      <TopNav page={page} navigate={navigate} />
      {page === "chat" ? <ChatPage openAdmin={() => navigate("admin")} /> : <AdminPage openChat={() => navigate("chat")} />}
    </div>
  );
}

function TopNav({ page, navigate }: { page: Page; navigate: (page: Page) => void }) {
  return (
    <nav className="topbar" aria-label="主导航">
      <button className="brand" onClick={() => navigate("chat")}>
        <Sparkles size={20} />
        <span>虚拟角色生命系统</span>
      </button>
      <div className="top-actions">
        <button className={page === "chat" ? "nav-pill active" : "nav-pill"} onClick={() => navigate("chat")}>
          <MessageCircle size={16} />
          用户聊天
        </button>
        <button className={page === "admin" ? "nav-pill active" : "nav-pill"} onClick={() => navigate("admin")}>
          <Settings2 size={16} />
          管理后台
        </button>
      </div>
    </nav>
  );
}

function ChatPage({ openAdmin }: { openAdmin: () => void }) {
  const [bundle, setBundle] = useState<CharacterBundle | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [content, setContent] = useState("");
  const [status, setStatus] = useState("连接中");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
  }, [messages, sending]);

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

  async function submit(text = content.trim()) {
    const finalText = text.trim();
    if (!finalText || !sessionId || sending) return;
    setContent("");
    setSending(true);
    setStatus("思考中");
    setError("");
    try {
      const result = await ChatApi.sendMessage(sessionId, finalText);
      const assistant = { ...result.assistantMessage, imageTasks: result.imageTasks || [] };
      setMessages((items) => [...items, result.userMessage, assistant]);
      setStatus(result.imageTasks?.length ? "生成中" : "在线");
      (result.imageTasks || []).forEach((task) => window.setTimeout(() => pollTask(task.id), 500));
      window.setTimeout(() => setStatus("在线"), 1800);
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
      inputRef.current?.focus();
    }
  }

  const profile = bundle?.profile;
  const avatar = profile?.avatarUrl;
  const quickPrompts = ["给我看看你的样子", "画一张你今天的照片", "please generate a photo"];

  return (
    <main className="chat-shell">
      <aside className="companion-panel">
        <div className="companion-card">
          <AvatarFrame avatar={avatar} name={profile?.name || "Mira"} size="large" />
          <div className="companion-copy">
            <p className="eyebrow">默认角色</p>
            <h1>{profile?.name || "Mira"}</h1>
            <p>{profile?.description || "一个温暖、敏锐、能陪你聊天并生成画面的虚拟角色。"}</p>
          </div>
          <div className="presence-grid">
            <Metric label="状态" value={status} />
            <Metric label="图像" value="异步生成" />
            <Metric label="记忆" value="当前会话" />
            <Metric label="端侧" value="Web / APK" />
          </div>
        </div>
      </aside>

      <section className="chat-panel">
        <header className="mobile-chat-header">
          <AvatarFrame avatar={avatar} name={profile?.name || "AI"} size="small" />
          <div className="mobile-title">
            <strong>{profile?.name || "正在连接角色"}</strong>
            <span>{status}</span>
          </div>
          <button className="icon-only ghost" onClick={openAdmin} aria-label="打开管理后台">
            <Settings2 size={20} />
          </button>
        </header>

        <header className="chat-intro">
          <div className="intro-main">
            <AvatarFrame avatar={avatar} name={profile?.name || "AI"} size="small" />
            <div>
              <h2>{profile?.name || "正在连接角色"}</h2>
              <p>{profile?.firstMessage || profile?.description || "直接开聊，或让角色根据对话生成图片。"}</p>
            </div>
          </div>
          <StatusBadge ok={status !== "离线"} text={status} />
        </header>

        <div className="message-list" ref={listRef}>
          {messages.length === 0 ? (
            <OpeningConversation
              name={profile?.name || "Mira"}
              description={profile?.firstMessage || "你好，我在这里。可以聊天，也可以把你的想象变成一张图。"}
              prompts={quickPrompts}
              onPick={submit}
              disabled={!sessionId || sending}
              error={error}
            />
          ) : (
            messages.map((message) => (
              <MessageBubble
                key={message.id}
                message={message}
                assistantName={profile?.name || "AI"}
                assistantAvatar={avatar}
                onRetry={pollTask}
                onPreview={setPreview}
              />
            ))
          )}
          {sending ? <ThinkingBubble avatar={avatar} name={profile?.name || "AI"} /> : null}
        </div>

        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <textarea
            ref={inputRef}
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
          <button className="primary send-button" disabled={!content.trim() || !sessionId || sending} aria-label="发送消息">
            {sending ? <Loader2 className="spin" size={20} /> : <Send size={20} />}
            <span>发送</span>
          </button>
        </form>
      </section>

      {preview ? (
        <div className="image-preview" role="dialog" aria-modal="true" onClick={() => setPreview("")}>
          <button className="icon-only preview-close" aria-label="关闭图片预览">
            <X size={22} />
          </button>
          <img src={preview} alt="生成图片预览" />
        </div>
      ) : null}
    </main>
  );
}

function OpeningConversation({
  name,
  description,
  prompts,
  disabled,
  error,
  onPick
}: {
  name: string;
  description: string;
  prompts: string[];
  disabled: boolean;
  error: string;
  onPick: (text: string) => void;
}) {
  return (
    <div className="opening">
      <div className="opening-bubble">
        <span className="mini-label">{name}</span>
        <p>{description}</p>
      </div>
      <div className="quick-prompts">
        {prompts.map((prompt) => (
          <button key={prompt} onClick={() => onPick(prompt)} disabled={disabled}>
            {prompt}
          </button>
        ))}
      </div>
      {error ? (
        <div className="inline-error">
          <CircleAlert size={16} />
          {error}
        </div>
      ) : null}
    </div>
  );
}

function ThinkingBubble({ avatar, name }: { avatar?: string | null; name: string }) {
  return (
    <article className="message-row assistant">
      <AvatarFrame avatar={avatar} name={name} size="tiny" />
      <div className="bubble thinking">
        <span />
        <span />
        <span />
      </div>
    </article>
  );
}

function MessageBubble({
  message,
  assistantName,
  assistantAvatar,
  onRetry,
  onPreview
}: {
  message: ChatMessage;
  assistantName: string;
  assistantAvatar?: string | null;
  onRetry: (taskId: string) => void;
  onPreview: (url: string) => void;
}) {
  const isUser = message.role === "user";
  return (
    <article className={isUser ? "message-row user" : "message-row assistant"}>
      {!isUser ? <AvatarFrame avatar={assistantAvatar} name={assistantName} size="tiny" /> : null}
      <div className="message-stack">
        <div className="bubble">
          <p>{message.content}</p>
          {(message.imageTasks || []).map((task) => (
            <ImageTaskCard key={task.id} task={task} onRetry={onRetry} onPreview={onPreview} />
          ))}
        </div>
        <time>{formatTime(message.createdAt)}</time>
      </div>
    </article>
  );
}

function ImageTaskCard({
  task,
  onRetry,
  onPreview
}: {
  task: ImageTask;
  onRetry: (taskId: string) => void;
  onPreview: (url: string) => void;
}) {
  if (task.status === "succeeded" && task.generatedAsset?.publicUrl) {
    const url = assetUrl(task.generatedAsset.publicUrl);
    return (
      <figure className="generated-image">
        <button type="button" onClick={() => onPreview(url)} aria-label="放大预览生成图片">
          <img src={url} alt="生成图片" />
        </button>
        <figcaption>
          <CheckCircle2 size={14} />
          生成完成
        </figcaption>
      </figure>
    );
  }
  if (task.status === "failed") {
    return (
      <div className="task-card failed">
        <XCircle size={18} />
        <div>
          <strong>图片生成失败</strong>
          <span>{friendlyImageError(task)}</span>
        </div>
        <button type="button" onClick={() => onRetry(task.id)}>
          <RotateCcw size={15} />
          重查
        </button>
      </div>
    );
  }
  return (
    <div className="task-card">
      <Loader2 className="spin" size={18} />
      <div>
        <strong>{task.status === "queued" ? "图片已排队" : "图片生成中"}</strong>
        <span>任务正在异步执行，完成后会自动显示在这里。</span>
      </div>
    </div>
  );
}

function AdminPage({ openChat }: { openChat: () => void }) {
  const [checking, setChecking] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [tab, setTab] = useState<AdminTab>("overview");
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(() => {
    let alive = true;
    async function check() {
      if (!getAdminToken()) {
        setChecking(false);
        return;
      }
      try {
        await AdminApi.me();
        if (alive) setAuthenticated(true);
      } catch {
        clearAdminToken();
      } finally {
        if (alive) setChecking(false);
      }
    }
    check();
    return () => {
      alive = false;
    };
  }, []);

  function notify(text: string, tone: Toast["tone"] = "info") {
    const toast = { id: Date.now() + Math.random(), text, tone };
    setToasts((items) => [...items, toast]);
    window.setTimeout(() => setToasts((items) => items.filter((item) => item.id !== toast.id)), 3600);
  }

  function logout() {
    clearAdminToken();
    setAuthenticated(false);
    notify("已退出管理员后台。", "info");
  }

  if (checking) {
    return (
      <main className="admin-loading">
        <LoadingState text="正在检查管理员登录状态" />
      </main>
    );
  }

  if (!authenticated) {
    return (
      <>
        <AdminLoginPage
          onSuccess={(token) => {
            setAdminToken(token);
            setAuthenticated(true);
            notify("登录成功，欢迎回来。", "success");
          }}
          openChat={openChat}
        />
        <ToastHost toasts={toasts} />
      </>
    );
  }

  const tabs: { id: AdminTab; label: string; icon: React.ReactNode }[] = [
    { id: "overview", label: "工作台", icon: <MonitorSmartphone size={17} /> },
    { id: "ai", label: "AI 助手", icon: <Sparkles size={17} /> },
    { id: "resources", label: "资源中心", icon: <RefreshCw size={17} /> },
    { id: "character", label: "角色", icon: <Bot size={17} /> },
    { id: "image", label: "生图", icon: <ImageIcon size={17} /> },
    { id: "workflow", label: "工作流", icon: <Workflow size={17} /> },
    { id: "model", label: "用户模型", icon: <Settings2 size={17} /> },
    { id: "test", label: "测试", icon: <TestTube2 size={17} /> }
  ];

  return (
    <main className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-title">
          <p className="eyebrow">管理后台</p>
          <h1>配置工作台</h1>
          <span>常用操作前置，复杂字段放进高级设置。</span>
        </div>
        <div className="admin-tabs">
          {tabs.map((item) => (
            <button key={item.id} className={tab === item.id ? "active" : ""} onClick={() => setTab(item.id)}>
              {item.icon}
              <span>{item.label}</span>
              <ChevronRight size={15} />
            </button>
          ))}
        </div>
        <div className="sidebar-actions">
          <button onClick={openChat}>
            <MessageCircle size={16} />
            返回聊天
          </button>
          <button onClick={logout}>
            <LogOut size={16} />
            退出
          </button>
        </div>
      </aside>

      <section className="admin-workspace">
        {tab === "overview" && <OverviewPanel notify={notify} setTab={setTab} />}
        {tab === "ai" && <AdminAIPanel notify={notify} />}
        {tab === "resources" && <ComfyResourcePanel notify={notify} />}
        {tab === "character" && <CharacterPanel notify={notify} />}
        {tab === "image" && <ImageConfigPanel notify={notify} />}
        {tab === "workflow" && <WorkflowPanel notify={notify} />}
        {tab === "model" && <ModelPanel notify={notify} />}
        {tab === "test" && <TestPanel notify={notify} />}
      </section>
      <ToastHost toasts={toasts} />
    </main>
  );
}

function AdminLoginPage({ onSuccess, openChat }: { onSuccess: (token: string) => void; openChat: () => void }) {
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function login(event: React.FormEvent) {
    event.preventDefault();
    if (!password.trim()) return;
    setSubmitting(true);
    setError("");
    try {
      const data = await AdminApi.login(password);
      onSuccess(data.token);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="login-icon">
          <LockKeyhole size={26} />
        </div>
        <p className="eyebrow">后台保护</p>
        <h1>登录管理后台</h1>
        <p>公网部署后，角色、模型和工作流配置都需要管理员密码才能修改。</p>
        <form onSubmit={login}>
          <label>
            <span>管理员密码</span>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入管理员密码"
              autoFocus
            />
          </label>
          {error ? (
            <div className="inline-error">
              <CircleAlert size={16} />
              {error}
            </div>
          ) : null}
          <button className="primary" disabled={submitting || !password.trim()}>
            {submitting ? <Loader2 className="spin" size={17} /> : <KeyRound size={17} />}
            登录
          </button>
          <button type="button" onClick={openChat}>
            <MessageCircle size={17} />
            先回聊天页
          </button>
        </form>
      </section>
    </main>
  );
}

function OverviewPanel({ notify, setTab }: { notify: (text: string, tone?: Toast["tone"]) => void; setTab: (tab: AdminTab) => void }) {
  const [llm, setLlm] = useState<any>(null);
  const [comfy, setComfy] = useState<any>(null);
  const [version, setVersion] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const [llmResult, comfyResult, versionResult] = await Promise.allSettled([
      AdminApi.llmHealth(),
      AdminApi.comfyuiHealth(),
      ChatApi.version()
    ]);
    if (llmResult.status === "fulfilled") setLlm(llmResult.value);
    if (comfyResult.status === "fulfilled") setComfy(comfyResult.value);
    if (versionResult.status === "fulfilled") setVersion(versionResult.value);
    if (llmResult.status === "rejected" || comfyResult.status === "rejected") {
      notify("部分服务不可用，请检查模型连接。", "error");
    }
    setLoading(false);
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <Panel
      title="运行工作台"
      kicker="Dashboard"
      action={
        <button onClick={load} disabled={loading}>
          {loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
          刷新状态
        </button>
      }
    >
      <div className="summary-grid">
        <SummaryCard
          title="LLM 连接"
          value={llm?.enabled ? "真实接口" : "Mock 模式"}
          ok={Boolean(llm?.ok)}
          detail={llm?.baseUrl || "未配置 Base URL"}
        />
        <SummaryCard
          title="ComfyUI"
          value={comfy?.enabled ? "真实接口" : "Mock 模式"}
          ok={Boolean(comfy?.ok)}
          detail={comfy?.baseUrl || "未配置 Base URL"}
        />
        <SummaryCard title="当前版本" value={version?.version || "0.4.0"} ok detail="Web / VPS / APK 同版本发布" />
        <SummaryCard title="后台保护" value="已启用" ok detail="管理员接口需要 Bearer Token" />
      </div>
      <div className="action-strip">
        <button className="primary" onClick={() => setTab("model")}>
          <Settings2 size={16} />
          配置模型
        </button>
        <button onClick={() => setTab("character")}>
          <Bot size={16} />
          修改角色
        </button>
        <button onClick={() => setTab("workflow")}>
          <Workflow size={16} />
          分析工作流
        </button>
        <button onClick={() => setTab("test")}>
          <TestTube2 size={16} />
          跑测试
        </button>
      </div>
      <div className="guide-list">
        <Step title="1. 模型连接" text="保存 OpenAI-compatible 接口，拉取模型并测试。" />
        <Step title="2. 角色配置" text="只维护名称、头像、简介、基础提示词和生图预设。" />
        <Step title="3. 链路测试" text="测试聊天与生图，失败时根据中文提示修复。" />
      </div>
    </Panel>
  );
}

function AdminAIPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [config, setConfig] = useState<AdminAIConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [characters, setCharacters] = useState<CharacterBundle[]>([]);
  const [templates, setTemplates] = useState<CharacterTemplate[]>([]);
  const [targetId, setTargetId] = useState("");
  const [seedText, setSeedText] = useState("温柔、有陪伴感、能根据聊天生成画面的虚拟角色");
  const [task, setTask] = useState<AITask | null>(null);
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    load().catch((err) => notify(errorText(err), "error"));
  }, []);

  async function load() {
    const [configData, characterData, templateData] = await Promise.all([
      AdminApi.getAdminAiConfig(),
      AdminApi.listCharacters(),
      AdminApi.listCharacterTemplates().catch(() => [])
    ]);
    setConfig(configData);
    setCharacters(characterData);
    setTemplates(templateData);
    setTargetId((current) => current || characterData[0]?.character.id || "");
  }

  async function saveConfig() {
    if (!config) return;
    try {
      const data = await AdminApi.saveAdminAiConfig({ ...config, apiKey: apiKey || undefined });
      setConfig(data);
      setApiKey("");
      setResult(JSON.stringify(data, null, 2));
      notify("后台 AI 配置已保存。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function testConfig() {
    try {
      const data = await AdminApi.testAdminAi("请用一句话说明你能帮助我完成哪些后台配置。");
      setResult(JSON.stringify(data, null, 2));
      notify("后台 AI 测试完成。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function listModels() {
    try {
      const data = await AdminApi.listAdminAiModels();
      setResult(JSON.stringify(data, null, 2));
      notify("后台 AI 模型列表已返回。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function runTask(type: string) {
    setBusy(true);
    try {
      const selected = characters.find((item) => item.character.id === targetId);
      const created = await AdminApi.createAiTask({
        type,
        targetType: type.includes("character") || type.includes("prompt") ? "character" : undefined,
        targetId: type.includes("character") || type.includes("prompt") ? targetId : undefined,
        inputSnapshot: {
          seedText,
          character: selected || null,
          note: "默认生成草稿，管理员确认后再应用。"
        },
        applyMode: "draft"
      });
      setTask(created);
      notify("AI 任务已创建，正在生成草稿。", "info");
      const done = await waitForAiTask(created.id);
      setTask(done);
      setResult(JSON.stringify(done.outputDraft || done, null, 2));
      notify(done.status === "succeeded" ? "AI 草稿已生成。" : "AI 任务失败，请查看原因。", done.status === "succeeded" ? "success" : "error");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    } finally {
      setBusy(false);
    }
  }

  async function applyDraft(overwrite: boolean) {
    if (!task) return;
    try {
      const data = await AdminApi.applyAiTask(task.id, overwrite);
      setResult(JSON.stringify(data, null, 2));
      notify(overwrite ? "AI 草稿已覆盖应用。" : "AI 草稿已按空字段应用。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  if (!config) {
    return (
      <Panel title="AI 助手" kicker="Admin AI">
        <LoadingState text="正在读取后台 AI 配置" />
      </Panel>
    );
  }

  return (
    <Panel title="AI 助手" kicker="Admin AI" action={<StatusBadge ok={config.enabled} text={config.enabled ? "真实后台 AI" : "Mock 草稿"} />}>
      <Alert>
        后台 AI 独立于用户聊天模型，主要用于角色库、提示词优化、生图预设建议和 Workflow 诊断。未启用时会明确显示 Mock 草稿，不会伪装成真实模型。
      </Alert>
      <div className="form-grid two">
        <label className="toggle-line">
          <input type="checkbox" checked={config.enabled} onChange={(event) => setConfig({ ...config, enabled: event.target.checked })} />
          <span>启用后台 AI</span>
        </label>
        <label>
          <span>Temperature</span>
          <input type="number" step="0.1" value={config.temperature || 0.4} onChange={(event) => setConfig({ ...config, temperature: Number(event.target.value) })} />
        </label>
        <label>
          <span>Base URL</span>
          <input value={config.baseUrl || ""} placeholder="https://example.com/v1" onChange={(event) => setConfig({ ...config, baseUrl: event.target.value })} />
        </label>
        <label>
          <span>模型 ID</span>
          <input value={config.model || ""} placeholder="留空时尝试使用模型列表第一个" onChange={(event) => setConfig({ ...config, model: event.target.value })} />
        </label>
        <label>
          <span>API Key</span>
          <input type="password" value={apiKey} placeholder={config.hasApiKey ? `已配置：${config.maskedApiKey}` : "可留空"} onChange={(event) => setApiKey(event.target.value)} />
        </label>
        <label>
          <span>超时秒数</span>
          <input type="number" value={config.timeout || 60} onChange={(event) => setConfig({ ...config, timeout: Number(event.target.value) })} />
        </label>
      </div>
      <div className="button-row">
        <button className="primary" onClick={saveConfig}><Save size={16} />保存后台 AI</button>
        <button onClick={listModels}><RefreshCw size={16} />拉取模型</button>
        <button onClick={testConfig}><TestTube2 size={16} />测试连接</button>
      </div>

      <div className="ai-workbench">
        <section>
          <p className="eyebrow">角色库</p>
          <div className="template-strip">
            {templates.slice(0, 4).map((item) => (
              <button key={item.id} onClick={() => setSeedText(`${item.name}：${item.description || ""}`)}>
                <Sparkles size={15} />
                {item.name}
              </button>
            ))}
          </div>
          <label>
            <span>灵感 / 待优化内容</span>
            <textarea value={seedText} onChange={(event) => setSeedText(event.target.value)} />
          </label>
          <label>
            <span>应用目标角色</span>
            <select value={targetId} onChange={(event) => setTargetId(event.target.value)}>
              {characters.map((item) => (
                <option key={item.character.id} value={item.character.id}>{item.profile.name}</option>
              ))}
            </select>
          </label>
        </section>
        <section className="ai-actions-grid">
          <button disabled={busy} onClick={() => runTask("character.generate")}><Wand2 size={16} />一键生成角色</button>
          <button disabled={busy} onClick={() => runTask("character.optimize")}><Bot size={16} />优化角色设定</button>
          <button disabled={busy} onClick={() => runTask("prompt.optimize")}><MessageCircle size={16} />优化角色提示词</button>
          <button disabled={busy} onClick={() => runTask("visual-prompt.optimize")}><ImageIcon size={16} />优化视觉提示词</button>
          <button disabled={busy} onClick={() => runTask("generation-preset.suggest")}><Settings2 size={16} />建议生图预设</button>
        </section>
      </div>
      {task ? (
        <div className="ai-task-status">
          <StatusBadge ok={task.status === "succeeded"} text={`任务：${task.type} / ${task.status}`} />
          <div className="button-row compact">
            <button onClick={() => applyDraft(false)} disabled={task.status !== "succeeded"}>只填空字段</button>
            <button className="primary" onClick={() => applyDraft(true)} disabled={task.status !== "succeeded"}>确认覆盖应用</button>
          </div>
        </div>
      ) : null}
      <ResultBox value={result} />
    </Panel>
  );
}

function ComfyResourcePanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [diagnostics, setDiagnostics] = useState<ComfyResourcesResponse | null>(null);
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    load().catch((err) => notify(errorText(err), "error"));
  }, []);

  async function load() {
    const data = await AdminApi.comfyDiagnostics();
    setDiagnostics(data);
  }

  async function refresh() {
    setLoading(true);
    try {
      const data = await AdminApi.refreshComfyResources();
      setDiagnostics(data);
      setResult(JSON.stringify(data, null, 2));
      notify(data.ok ? "ComfyUI 资源已刷新。" : "刷新失败，已显示缓存资源。", data.ok ? "success" : "error");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    } finally {
      setLoading(false);
    }
  }

  const resources = diagnostics?.resources || {};
  const types = ["checkpoints", "loras", "vae", "samplers", "schedulers", "embeddings", "customNodes", "nodeObjectInfo", "queue", "systemStats"];

  return (
    <Panel title="ComfyUI 资源中心" kicker="Resources" action={<button onClick={refresh} disabled={loading}>{loading ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}刷新资源</button>}>
      <div className="summary-grid">
        <SummaryCard title="连接状态" value={diagnostics?.ok ? "可用" : "异常"} ok={Boolean(diagnostics?.ok)} detail={diagnostics?.baseUrl || "未配置 Base URL"} />
        <SummaryCard title="运行模式" value={diagnostics?.mode || "未知"} ok={diagnostics?.mode !== "cache"} detail={diagnostics?.nextStep || diagnostics?.message || "实时读取失败时会使用缓存"} />
        <SummaryCard title="资源缓存" value={`${types.filter((type) => itemCount(resources[type]) > 0).length} 类`} ok detail="失败时保留上次成功缓存" />
      </div>
      {diagnostics?.errorMessage ? <Alert>{diagnostics.errorMessage}</Alert> : null}
      <div className="resource-grid">
        {types.map((type) => {
          const resource = resources[type];
          return (
            <div className="resource-card" key={type}>
              <strong>{type}</strong>
              <span>{itemCount(resource)} 项</span>
              <small>{resource?.source || "empty"} {resource?.fetchedAt ? `· ${new Date(resource.fetchedAt).toLocaleString()}` : ""}</small>
              {resource?.errorMessage ? <em>{resource.errorMessage}</em> : null}
            </div>
          );
        })}
      </div>
      <details className="advanced">
        <summary>原始资源与诊断结果</summary>
        <ResultBox value={result || JSON.stringify(diagnostics, null, 2)} />
      </details>
    </Panel>
  );
}

function CharacterPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [items, setItems] = useState<CharacterBundle[]>([]);
  const [selected, setSelected] = useState<CharacterBundle | null>(null);
  const [seedText, setSeedText] = useState("温柔、聪明、会陪用户聊天并生成画面的虚拟角色");
  const [result, setResult] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load().catch((err) => notify(errorText(err), "error"));
  }, []);

  async function load() {
    const data = await AdminApi.listCharacters();
    setItems(data);
    setSelected((current) => data.find((item) => item.character.id === current?.character.id) || data[0] || null);
  }

  function patch(path: string, value: any) {
    if (!selected) return;
    const next = clone(selected);
    const parts = path.split(".");
    let cursor: any = next;
    parts.slice(0, -1).forEach((part) => {
      cursor = cursor[part];
    });
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
      notify("角色配置已保存。", "success");
      await load();
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
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
      notify("角色卡草稿已填入表单，保存后才会生效。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function publish() {
    if (!selected) return;
    try {
      const data = await AdminApi.publishCharacter(selected.character.id);
      setResult(JSON.stringify(data, null, 2));
      notify("角色已发布。", "success");
      await load();
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  if (!selected) {
    return (
      <Panel title="角色配置" kicker="Character">
        <LoadingState text="正在加载角色配置" />
      </Panel>
    );
  }

  return (
    <Panel title="角色配置" kicker="Character" action={<StatusBadge ok text={`v${selected.character.version || 1}`} />}>
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
          <input value={selected.visual.generationPresetId || ""} onChange={(event) => patch("visual.generationPresetId", event.target.value)} />
        </label>
        <label>
          <span>角色名称</span>
          <input value={selected.profile.name || ""} onChange={(event) => patch("profile.name", event.target.value)} />
        </label>
        <label>
          <span>头像 URL</span>
          <input value={selected.profile.avatarUrl || ""} onChange={(event) => patch("profile.avatarUrl", event.target.value)} />
        </label>
      </div>
      <label>
        <span>简介</span>
        <textarea value={selected.profile.description || ""} onChange={(event) => patch("profile.description", event.target.value)} />
      </label>
      <label>
        <span>基础角色提示词</span>
        <textarea value={selected.prompt.roleplayPrompt || ""} onChange={(event) => patch("prompt.roleplayPrompt", event.target.value)} />
      </label>
      <label>
        <span>视觉提示词</span>
        <textarea value={selected.visual.visualPrompt || ""} onChange={(event) => patch("visual.visualPrompt", event.target.value)} />
      </label>

      <details className="advanced">
        <summary>高级设置：系统提示词、安全提示词、角色卡草稿</summary>
        <label>
          <span>systemPrompt</span>
          <textarea value={selected.prompt.systemPrompt || ""} onChange={(event) => patch("prompt.systemPrompt", event.target.value)} />
        </label>
        <label>
          <span>safetyPrompt</span>
          <textarea value={selected.prompt.safetyPrompt || ""} onChange={(event) => patch("prompt.safetyPrompt", event.target.value)} />
        </label>
        <div className="form-grid two">
          <label>
            <span>角色卡灵感</span>
            <textarea value={seedText} onChange={(event) => setSeedText(event.target.value)} />
          </label>
          <div className="mini-action-card">
            <Wand2 size={20} />
            <strong>LLM 生成角色卡</strong>
            <span>生成结果只是草稿，不会自动发布。</span>
            <button onClick={generateCard}>生成并填入表单</button>
          </div>
        </div>
      </details>

      <div className="button-row">
        <button className="primary" onClick={save} disabled={saving}>
          {saving ? <Loader2 className="spin" size={16} /> : <Save size={16} />}
          保存角色
        </button>
        <button onClick={publish}>
          <ClipboardCheck size={16} />
          发布角色
        </button>
      </div>
      <ResultBox value={result} />
    </Panel>
  );
}

function ImageConfigPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [presets, setPresets] = useState<GenerationPreset[]>([]);
  const [preset, setPreset] = useState<GenerationPreset | null>(null);
  const [resources, setResources] = useState<ComfyResourcesResponse["resources"]>({});
  const [result, setResult] = useState("");

  useEffect(() => {
    load().catch((err) => notify(errorText(err), "error"));
  }, []);

  async function load() {
    const [data, resourceData] = await Promise.all([
      AdminApi.listGenerationPresets(),
      AdminApi.listComfyResources().catch(() => ({ resources: {} as ComfyResourcesResponse["resources"] }))
    ]);
    setPresets(data);
    setResources(resourceData.resources || {});
    setPreset((current) => data.find((item) => item.id === current?.id) || data[0] || null);
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
      notify("生图预设已保存。", "success");
      await load();
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  if (!preset) {
    return (
      <Panel title="生图配置" kicker="Generation">
        <LoadingState text="正在加载生图预设" />
      </Panel>
    );
  }

  return (
    <Panel title="生图配置" kicker="Generation Preset" action={<button onClick={load}><RefreshCw size={16} />刷新</button>}>
      <label>
        <span>选择预设</span>
        <select value={preset.id} onChange={(event) => setPreset(presets.find((item) => item.id === event.target.value) || null)}>
          {presets.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid two">
        <label>
          <span>预设名称</span>
          <input value={preset.name || ""} onChange={(event) => update("name", event.target.value)} />
        </label>
        <label>
          <span>Checkpoint</span>
          <ResourceSelect
            value={preset.checkpoint || ""}
            options={resourceOptions(resources, "checkpoints")}
            fallbackLabel="手动输入 Checkpoint"
            onChange={(value) => update("checkpoint", value)}
          />
        </label>
        <label>
          <span>宽度</span>
          <input type="number" value={preset.width || 768} onChange={(event) => update("width", Number(event.target.value))} />
        </label>
        <label>
          <span>高度</span>
          <input type="number" value={preset.height || 1024} onChange={(event) => update("height", Number(event.target.value))} />
        </label>
        <label>
          <span>步数</span>
          <input type="number" value={preset.steps || 24} onChange={(event) => update("steps", Number(event.target.value))} />
        </label>
        <label>
          <span>CFG</span>
          <input type="number" step="0.1" value={preset.cfg || 7} onChange={(event) => update("cfg", Number(event.target.value))} />
        </label>
      </div>
      <label>
        <span>反向提示词</span>
        <textarea value={preset.negativePrompt || ""} onChange={(event) => update("negativePrompt", event.target.value)} />
      </label>
      <details className="advanced">
        <summary>高级设置：LoRA、采样器、Seed、提示词前后缀</summary>
        <div className="form-grid two">
          <label>
            <span>Sampler</span>
            <ResourceSelect value={preset.sampler || ""} options={resourceOptions(resources, "samplers")} fallbackLabel="手动输入 Sampler" onChange={(value) => update("sampler", value)} />
          </label>
          <label>
            <span>Scheduler</span>
            <ResourceSelect value={preset.scheduler || ""} options={resourceOptions(resources, "schedulers")} fallbackLabel="手动输入 Scheduler" onChange={(value) => update("scheduler", value)} />
          </label>
          <label>
            <span>Seed 模式</span>
            <input value={preset.seedMode || "random"} onChange={(event) => update("seedMode", event.target.value)} />
          </label>
          <label>
            <span>WorkflowTemplate ID</span>
            <input value={preset.workflowTemplateId || ""} onChange={(event) => update("workflowTemplateId", event.target.value)} />
          </label>
        </div>
        <JsonTextarea label="LoRA 列表 JSON" value={preset.loras || []} onCommit={(value) => update("loras", value)} />
        <label>
          <span>正向提示词前缀</span>
          <textarea value={preset.positivePromptPrefix || ""} onChange={(event) => update("positivePromptPrefix", event.target.value)} />
        </label>
        <label>
          <span>正向提示词后缀</span>
          <textarea value={preset.positivePromptSuffix || ""} onChange={(event) => update("positivePromptSuffix", event.target.value)} />
        </label>
      </details>
      <div className="button-row">
        <button className="primary" onClick={save}>
          <Save size={16} />
          保存预设
        </button>
      </div>
      <ResultBox value={result} />
    </Panel>
  );
}

function WorkflowPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [mappings, setMappings] = useState<NodeMapping[]>([]);
  const [workflow, setWorkflow] = useState<WorkflowTemplate | null>(null);
  const [mapping, setMapping] = useState<NodeMapping | null>(null);
  const [analysis, setAnalysis] = useState<WorkflowTypedAnalysis | null>(null);
  const [result, setResult] = useState("");

  useEffect(() => {
    load().catch((err) => notify(errorText(err), "error"));
  }, []);

  async function load() {
    const [workflowData, mappingData] = await Promise.all([AdminApi.listWorkflowTemplates(), AdminApi.listNodeMappings()]);
    setWorkflows(workflowData);
    setMappings(mappingData);
    setWorkflow((current) => workflowData.find((item) => item.id === current?.id) || workflowData[0] || null);
    setMapping((current) => mappingData.find((item) => item.id === current?.id) || mappingData[0] || null);
  }

  async function analyze() {
    if (!workflow) return;
    try {
      const data = await AdminApi.parseWorkflow(workflow.workflowJson);
      setAnalysis(data);
      const nextMapping = data.typedMapping || data.guessedMapping || {};
      setResult(JSON.stringify({ diagnosis: data.diagnosis, nodeMapping: nextMapping }, null, 2));
      if (mapping) setMapping({ ...mapping, mappings: nextMapping });
      notify("Workflow 已完成类型化解析，映射草稿已填入。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
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
      notify("Workflow 与 NodeMapping 已保存。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function validate() {
    if (!workflow || !mapping) return;
    try {
      const data = await AdminApi.validateNodeMappingTyped(mapping.id, { workflowJson: workflow.workflowJson, mappings: mapping.mappings });
      setResult(JSON.stringify(data, null, 2));
      notify(data.valid ? "NodeMapping 类型化校验通过。" : "NodeMapping 校验发现问题，请查看修复建议。", data.valid ? "success" : "error");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  if (!workflow || !mapping) {
    return (
      <Panel title="工作流配置" kicker="Workflow">
        <LoadingState text="正在加载 Workflow 与 NodeMapping" />
      </Panel>
    );
  }

  return (
    <Panel title="工作流配置" kicker="Workflow Wizard" action={<button onClick={load}><RefreshCw size={16} />刷新</button>}>
      <div className="wizard-steps">
        <Step title="1. 粘贴 Workflow" text="使用 ComfyUI 导出的 API Format JSON。" />
        <Step title="2. 自动分析节点" text="系统展示节点并猜测关键映射。" />
        <Step title="3. 手动校验保存" text="必要时修正 NodeMapping，再保存。" />
      </div>
      <div className="form-grid two">
        <label>
          <span>Workflow</span>
          <select value={workflow.id} onChange={(event) => setWorkflow(workflows.find((item) => item.id === event.target.value) || null)}>
            {workflows.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>NodeMapping</span>
          <select value={mapping.id} onChange={(event) => setMapping(mappings.find((item) => item.id === event.target.value) || null)}>
            {mappings.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <details className="advanced" open>
        <summary>高级设置：workflowJson 与 NodeMapping JSON</summary>
        <JsonTextarea label="workflowJson（ComfyUI API Format）" value={workflow.workflowJson} onCommit={(value) => setWorkflow({ ...workflow, workflowJson: value })} rows={12} />
        <JsonTextarea label="mappings JSON" value={mapping.mappings} onCommit={(value) => setMapping({ ...mapping, mappings: value })} rows={10} />
      </details>
      <div className="button-row">
        <button className="primary" onClick={analyze}>
          <Wand2 size={16} />
          分析 Workflow
        </button>
        <button onClick={saveAll}>
          <Save size={16} />
          保存配置
        </button>
        <button onClick={validate}>
          <ShieldCheck size={16} />
          校验 NodeMapping
        </button>
      </div>
      {analysis ? (
        <div className="node-grid">
          {analysis.nodes.slice(0, 16).map((node) => (
            <div className="node-card" key={node.nodeId}>
              <strong>{node.nodeId}</strong>
              <span>{node.classType}</span>
              <code>{(node as any).inputNames?.join(", ") || Object.keys((node as any).inputs || {}).join(", ") || "无 inputs"}</code>
            </div>
          ))}
        </div>
      ) : null}
      <ResultBox value={result} />
    </Panel>
  );
}

function ModelPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [config, setConfig] = useState<LLMConfig | null>(null);
  const [apiKey, setApiKey] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    AdminApi.getLlmConfig()
      .then(setConfig)
      .catch((err) => notify(errorText(err), "error"));
  }, []);

  async function save() {
    if (!config) return;
    try {
      const data = await AdminApi.saveLlmConfig({ ...config, apiKey: apiKey || undefined });
      setConfig(data);
      setApiKey("");
      setResult(JSON.stringify(data, null, 2));
      notify("模型连接配置已保存。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function listModels() {
    try {
      const data = await AdminApi.listLlmModels();
      setResult(JSON.stringify(data, null, 2));
      notify("模型列表请求完成。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function testModel() {
    try {
      const data = await AdminApi.testLlm("请用一句话确认模型连接正常，并说明你可以帮助定义角色。");
      setResult(JSON.stringify(data, null, 2));
      notify("模型测试完成。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  if (!config) {
    return (
      <Panel title="模型连接" kicker="LLM">
        <LoadingState text="正在读取模型配置" />
      </Panel>
    );
  }

  return (
    <Panel title="模型连接" kicker="OpenAI-compatible" action={<StatusBadge ok={config.enabled} text={config.enabled ? "真实 LLM" : "Mock 模式"} />}>
      <Alert>
        后台 LLM 主要用于角色定义、角色卡生成、工作流分析和聊天决策。生产环境请使用自定义 OpenAI-compatible 接口；ChatGPT Plus/Codex
        额度适合开发工作流，不作为后端生产 API 用量来源。
      </Alert>
      <div className="form-grid two">
        <label className="toggle-line">
          <input type="checkbox" checked={config.enabled} onChange={(event) => setConfig({ ...config, enabled: event.target.checked })} />
          <span>启用真实 LLM</span>
        </label>
        <label>
          <span>超时秒数</span>
          <input type="number" value={config.timeout || 60} onChange={(event) => setConfig({ ...config, timeout: Number(event.target.value) })} />
        </label>
        <label>
          <span>Base URL</span>
          <input value={config.baseUrl || ""} placeholder="https://example.com/v1" onChange={(event) => setConfig({ ...config, baseUrl: event.target.value })} />
        </label>
        <label>
          <span>模型 ID</span>
          <input value={config.model || ""} placeholder="留空时后端尝试使用第一个模型" onChange={(event) => setConfig({ ...config, model: event.target.value })} />
        </label>
        <label>
          <span>API Key</span>
          <input
            type="password"
            value={apiKey}
            placeholder={config.hasApiKey ? `已配置：${config.maskedApiKey}` : "可留空"}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>
      </div>
      <div className="button-row">
        <button className="primary" onClick={save}>
          <Save size={16} />
          保存模型配置
        </button>
        <button onClick={listModels}>
          <RefreshCw size={16} />
          拉取模型
        </button>
        <button onClick={testModel}>
          <TestTube2 size={16} />
          测试连接
        </button>
      </div>
      <ResultBox value={result} />
    </Panel>
  );
}

function TestPanel({ notify }: { notify: (text: string, tone?: Toast["tone"]) => void }) {
  const [characters, setCharacters] = useState<CharacterBundle[]>([]);
  const [characterId, setCharacterId] = useState("");
  const [chatText, setChatText] = useState("请生成一段适合角色的开场白，并判断是否需要生图。");
  const [imageText, setImageText] = useState("portrait of the default character, warm light, expressive eyes");
  const [result, setResult] = useState("");
  const [imageUrl, setImageUrl] = useState("");

  useEffect(() => {
    AdminApi.listCharacters()
      .then((data) => {
        setCharacters(data);
        setCharacterId(data[0]?.character.id || "");
      })
      .catch((err) => notify(errorText(err), "error"));
  }, []);

  async function testChat() {
    try {
      const data = await AdminApi.testChat(characterId, chatText);
      setResult(JSON.stringify(data, null, 2));
      notify("测试聊天完成。", "success");
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  async function testImage() {
    try {
      setImageUrl("");
      const task = await AdminApi.testImage(characterId, imageText);
      setResult(JSON.stringify(task, null, 2));
      notify("图片任务已提交，正在轮询结果。", "info");
      const finalTask = await waitForTask(task.id);
      setResult(JSON.stringify(finalTask, null, 2));
      if (finalTask.generatedAsset?.publicUrl) {
        setImageUrl(assetUrl(finalTask.generatedAsset.publicUrl));
        notify("测试生图完成。", "success");
      } else if (finalTask.status === "failed") {
        notify(friendlyImageError(finalTask), "error");
      }
    } catch (err) {
      const text = errorText(err);
      setResult(text);
      notify(text, "error");
    }
  }

  return (
    <Panel title="测试中心" kicker="Test Center">
      <label>
        <span>测试角色</span>
        <select value={characterId} onChange={(event) => setCharacterId(event.target.value)}>
          {characters.map((item) => (
            <option key={item.character.id} value={item.character.id}>
              {item.profile.name}
            </option>
          ))}
        </select>
      </label>
      <div className="form-grid two">
        <label>
          <span>测试聊天 / 角色定义</span>
          <textarea value={chatText} onChange={(event) => setChatText(event.target.value)} />
        </label>
        <label>
          <span>测试画面描述</span>
          <textarea value={imageText} onChange={(event) => setImageText(event.target.value)} />
        </label>
      </div>
      <div className="button-row">
        <button className="primary" onClick={testChat}>
          <MessageCircle size={16} />
          测试聊天
        </button>
        <button onClick={testImage}>
          <ImageIcon size={16} />
          测试生图
        </button>
      </div>
      {imageUrl ? (
        <figure className="test-preview">
          <img src={imageUrl} alt="测试生成结果" />
          <figcaption>测试生成结果</figcaption>
        </figure>
      ) : null}
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

async function waitForAiTask(taskId: string) {
  for (let index = 0; index < 90; index += 1) {
    const task = await AdminApi.getAiTask(taskId);
    if (["succeeded", "failed"].includes(task.status)) return task;
    await new Promise((resolve) => window.setTimeout(resolve, 1200));
  }
  throw new Error("AI 任务等待超时");
}

function itemCount(resource?: ComfyResourcesResponse["resources"][string]) {
  const items = resource?.items;
  if (Array.isArray(items)) return items.length;
  if (items && typeof items === "object") return Object.keys(items as Record<string, unknown>).length;
  return items ? 1 : 0;
}

function resourceOptions(resources: ComfyResourcesResponse["resources"], type: string) {
  const items = resources?.[type]?.items;
  if (Array.isArray(items)) {
    return items
      .map((item) => (typeof item === "string" ? item : String((item as any)?.name || (item as any)?.id || "")))
      .filter(Boolean);
  }
  if (items && typeof items === "object") {
    return Object.keys(items as Record<string, unknown>);
  }
  return [];
}

function Panel({ title, kicker, action, children }: { title: string; kicker: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <p className="eyebrow">{kicker}</p>
          <h2>{title}</h2>
        </div>
        {action ? <div className="panel-action">{action}</div> : null}
      </header>
      {children}
    </section>
  );
}

function SummaryCard({ title, value, detail, ok }: { title: string; value: string; detail: string; ok: boolean }) {
  return (
    <div className={ok ? "summary-card ok-card" : "summary-card bad-card"}>
      {ok ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
      <span>{title}</span>
      <strong>{value}</strong>
      <p>{detail}</p>
    </div>
  );
}

function StatusBadge({ ok, text }: { ok: boolean; text: string }) {
  return <span className={ok ? "status ok" : "status bad"}>{text}</span>;
}

function ResourceSelect({
  value,
  options,
  fallbackLabel,
  onChange
}: {
  value: string;
  options: string[];
  fallbackLabel: string;
  onChange: (value: string) => void;
}) {
  const [manual, setManual] = useState(!options.length || (value && !options.includes(value)));
  useEffect(() => {
    setManual(!options.length || (value ? !options.includes(value) : false));
  }, [options.join("|"), value]);
  if (manual) {
    return (
      <div className="resource-select">
        <input value={value} placeholder={fallbackLabel} onChange={(event) => onChange(event.target.value)} />
        {options.length ? <button type="button" onClick={() => setManual(false)}>选择资源</button> : null}
      </div>
    );
  }
  return (
    <div className="resource-select">
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">请选择</option>
        {options.map((item) => (
          <option key={item} value={item}>{item}</option>
        ))}
      </select>
      <button type="button" onClick={() => setManual(true)}>手动</button>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Step({ title, text }: { title: string; text: string }) {
  return (
    <div className="step">
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function Alert({ children }: { children: React.ReactNode }) {
  return (
    <div className="alert">
      <CircleAlert size={18} />
      <span>{children}</span>
    </div>
  );
}

function LoadingState({ text }: { text: string }) {
  return (
    <div className="loading-state">
      <Loader2 className="spin" />
      {text}
    </div>
  );
}

function ResultBox({ value }: { value: string }) {
  return value ? <pre className="result-box">{value}</pre> : null;
}

function JsonTextarea({
  label,
  value,
  onCommit,
  rows = 6
}: {
  label: string;
  value: any;
  onCommit: (value: any) => void;
  rows?: number;
}) {
  const [raw, setRaw] = useState(() => JSON.stringify(value ?? {}, null, 2));
  const [error, setError] = useState("");

  useEffect(() => {
    setRaw(JSON.stringify(value ?? {}, null, 2));
    setError("");
  }, [value]);

  function commit() {
    try {
      onCommit(JSON.parse(raw));
      setError("");
    } catch {
      setError("JSON 格式暂未合法，修正后再保存。");
    }
  }

  return (
    <label>
      <span>{label}</span>
      <textarea rows={rows} value={raw} onChange={(event) => setRaw(event.target.value)} onBlur={commit} spellCheck={false} />
      <div className="json-footer">
        {error ? <em className="field-error">{error}</em> : <span>失焦后自动应用 JSON。</span>}
        <button type="button" onClick={commit}>
          应用 JSON
        </button>
      </div>
    </label>
  );
}

function AvatarFrame({ avatar, name, size }: { avatar?: string | null; name: string; size: "large" | "small" | "tiny" }) {
  const initials = name.slice(0, 2).toUpperCase();
  return (
    <div className={`avatar avatar-${size}`}>
      {avatar ? <img src={avatar} alt={`${name} 头像`} /> : <span>{initials}</span>}
    </div>
  );
}

function ToastHost({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="toast-host">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast ${toast.tone}`}>
          {toast.tone === "success" ? <CheckCircle2 size={17} /> : toast.tone === "error" ? <XCircle size={17} /> : <CircleAlert size={17} />}
          {toast.text}
        </div>
      ))}
    </div>
  );
}

function formatTime(value?: string) {
  if (!value) return "";
  try {
    return new Intl.DateTimeFormat("zh-CN", { hour: "2-digit", minute: "2-digit" }).format(new Date(value));
  } catch {
    return "";
  }
}

function assetUrl(url: string) {
  if (!url || url.startsWith("http://") || url.startsWith("https://") || url.startsWith("data:")) return url;
  if (url.startsWith("/")) return `${API_BASE}${url}`;
  return url;
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

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

createRoot(document.getElementById("root")!).render(<App />);
