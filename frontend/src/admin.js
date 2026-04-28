(function () {
  const state = {
    characters: [],
    presets: [],
    workflows: [],
    mappings: [],
    selectedCharacter: null,
    selectedPreset: null,
    selectedWorkflow: null,
    selectedMapping: null,
    generatedCard: null,
    guessedMapping: null,
  };

  const $ = (id) => document.getElementById(id);

  function toast(message, ok = true) {
    const target = $("adminToast");
    if (!target) return;
    target.hidden = false;
    target.textContent = message;
    target.classList.toggle("is-error", !ok);
    window.clearTimeout(toast.timer);
    toast.timer = window.setTimeout(() => {
      target.hidden = true;
    }, 4200);
  }

  function show(target, data, ok = true) {
    target.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    target.classList.toggle("is-error", !ok);
    target.classList.remove("flash");
    window.requestAnimationFrame(() => target.classList.add("flash"));
  }

  function setHealth(prefix, data, ok) {
    $(`${prefix}Status`).textContent = ok
      ? data.enabled
        ? "\u5df2\u8fde\u63a5"
        : "Mock \u6a21\u5f0f"
      : "\u4e0d\u53ef\u7528";
    $(`${prefix}Status`).className = ok ? "health-ok" : "health-error";
    $(`${prefix}BaseUrl`).textContent = data?.baseUrl || "";
  }

  function parseJsonField(id, fallback) {
    const raw = $(id).value.trim();
    if (!raw) return fallback;
    return JSON.parse(raw);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function workflowNodes(workflow) {
    if (!workflow || typeof workflow !== "object" || Array.isArray(workflow)) return [];
    return Object.entries(workflow)
      .filter(([, node]) => node && typeof node === "object")
      .map(([nodeId, node]) => ({
        nodeId: String(nodeId),
        classType: node.class_type || node.classType || "",
        inputs: node.inputs || {},
        raw: node,
      }));
  }

  function nodeHasInput(node, key) {
    return node.inputs && Object.prototype.hasOwnProperty.call(node.inputs, key);
  }

  function guessWorkflowMapping(workflow) {
    const nodes = workflowNodes(workflow);
    const mapping = {};
    const textNodes = nodes.filter((node) => {
      const cls = node.classType.toLowerCase();
      return cls.includes("cliptextencode") || nodeHasInput(node, "text");
    });
    const negativeWords = ["negative", "low quality", "bad", "blurry", "worst", "deformed"];
    const negativeNode =
      textNodes.find((node) => negativeWords.some((word) => String(node.inputs.text || "").toLowerCase().includes(word))) ||
      textNodes[1];
    const positiveNode = textNodes.find((node) => node !== negativeNode) || textNodes[0];

    if (positiveNode) mapping.positivePrompt = { nodeId: positiveNode.nodeId, inputPath: "inputs.text" };
    if (negativeNode) mapping.negativePrompt = { nodeId: negativeNode.nodeId, inputPath: "inputs.text" };

    const checkpointNode = nodes.find((node) => {
      const cls = node.classType.toLowerCase();
      return cls.includes("checkpoint") || nodeHasInput(node, "ckpt_name");
    });
    if (checkpointNode) mapping.checkpoint = { nodeId: checkpointNode.nodeId, inputPath: "inputs.ckpt_name" };

    const latentNode = nodes.find((node) => {
      const cls = node.classType.toLowerCase();
      return cls.includes("emptylatentimage") || (nodeHasInput(node, "width") && nodeHasInput(node, "height"));
    });
    if (latentNode) {
      mapping.width = { nodeId: latentNode.nodeId, inputPath: "inputs.width" };
      mapping.height = { nodeId: latentNode.nodeId, inputPath: "inputs.height" };
    }

    const samplerNode = nodes.find((node) => {
      const cls = node.classType.toLowerCase();
      return cls.includes("ksampler") || (nodeHasInput(node, "seed") && nodeHasInput(node, "steps") && nodeHasInput(node, "cfg"));
    });
    if (samplerNode) {
      if (nodeHasInput(samplerNode, "seed")) mapping.seed = { nodeId: samplerNode.nodeId, inputPath: "inputs.seed" };
      if (nodeHasInput(samplerNode, "steps")) mapping.steps = { nodeId: samplerNode.nodeId, inputPath: "inputs.steps" };
      if (nodeHasInput(samplerNode, "cfg")) mapping.cfg = { nodeId: samplerNode.nodeId, inputPath: "inputs.cfg" };
      if (nodeHasInput(samplerNode, "sampler_name")) mapping.sampler = { nodeId: samplerNode.nodeId, inputPath: "inputs.sampler_name" };
      if (nodeHasInput(samplerNode, "scheduler")) mapping.scheduler = { nodeId: samplerNode.nodeId, inputPath: "inputs.scheduler" };
    }

    return mapping;
  }

  function renderWorkflowAnalysis(workflow) {
    const nodes = workflowNodes(workflow);
    $("workflowNodeList").innerHTML = nodes
      .map(
        (node) => `
          <div class="node-card">
            <div><strong>${escapeHtml(node.nodeId)}</strong> <code>${escapeHtml(node.classType || "unknown")}</code></div>
            <pre>${escapeHtml(JSON.stringify(node.inputs, null, 2))}</pre>
          </div>
        `
      )
      .join("");
    state.guessedMapping = guessWorkflowMapping(workflow);
    $("mappingGuessResult").textContent = JSON.stringify(state.guessedMapping, null, 2);
  }

  function analyzeWorkflowFromField() {
    try {
      const workflow = parseJsonField("workflowJson", {});
      renderWorkflowAnalysis(workflow);
      show($("workflowResult"), { analyzedNodes: workflowNodes(workflow).length, guessedMapping: state.guessedMapping });
      return workflow;
    } catch (error) {
      $("workflowNodeList").innerHTML = "";
      state.guessedMapping = null;
      show($("mappingGuessResult"), { error: error.message }, false);
      show($("workflowResult"), { error: error.message }, false);
      return null;
    }
  }

  function optionLabel(item, fallback) {
    const suffix = item.isDefault ? " default" : "";
    return `${item.name || item.profile?.name || item.code || fallback}${suffix} (${item.id})`;
  }

  function fallbackLabel(fallback) {
    const labels = {
      character: "\u89d2\u8272",
      preset: "\u9884\u8bbe",
      workflow: "Workflow",
      mapping: "NodeMapping",
    };
    return labels[fallback] || fallback;
  }

  function fillSelect(select, items, fallback) {
    select.innerHTML = "";
    const createOption = document.createElement("option");
    createOption.value = "";
    createOption.textContent = `+ \u65b0\u5efa ${fallbackLabel(fallback)}`;
    select.appendChild(createOption);
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.character?.id || item.id;
      option.textContent = optionLabel(item.character ? { ...item.character, name: item.profile?.name } : item, fallback);
      select.appendChild(option);
    });
  }

  function currentCharacterId() {
    return $("characterSelect").value;
  }

  function fillCharacterForm(bundle) {
    state.selectedCharacter = bundle;
    const profile = bundle?.profile || {};
    const prompt = bundle?.prompt || {};
    const visual = bundle?.visual || {};
    $("characterName").value = profile.name || "";
    $("avatarUrl").value = profile.avatarUrl || "";
    $("description").value = profile.description || "";
    $("systemPrompt").value = prompt.systemPrompt || "";
    $("characterPrompt").value = prompt.roleplayPrompt || "";
    $("visualPrompt").value = visual.visualPrompt || "";
    $("generationPresetId").value = visual.generationPresetId || state.presets[0]?.id || "";
  }

  function newCharacterForm() {
    state.selectedCharacter = null;
    $("characterSelect").value = "";
    $("characterName").value = "New Character";
    $("avatarUrl").value = "";
    $("description").value = "";
    $("systemPrompt").value = "You are a virtual character.";
    $("characterPrompt").value = "Stay in character and answer naturally.";
    $("visualPrompt").value = "virtual character portrait";
    $("generationPresetId").value = state.presets[0]?.id || "";
  }

  function characterPayload() {
    const existing = state.selectedCharacter?.character;
    return {
      code: existing?.code || `character_${Date.now()}`,
      profile: {
        name: $("characterName").value.trim() || "Mock Character",
        avatarUrl: $("avatarUrl").value.trim() || null,
        description: $("description").value.trim() || null,
        personality: state.selectedCharacter?.profile?.personality || "",
        scenario: state.selectedCharacter?.profile?.scenario || "",
        firstMessage: state.selectedCharacter?.profile?.firstMessage || "",
        tags: state.selectedCharacter?.profile?.tags || [],
      },
      prompt: {
        systemPrompt: $("systemPrompt").value.trim() || "You are a virtual character.",
        roleplayPrompt: $("characterPrompt").value.trim() || "Stay in character.",
        conversationStyle: state.selectedCharacter?.prompt?.conversationStyle || "",
        safetyPrompt: state.selectedCharacter?.prompt?.safetyPrompt || "",
      },
      visual: {
        visualPrompt: $("visualPrompt").value.trim() || "virtual character portrait",
        visualNegativePrompt: state.selectedCharacter?.visual?.visualNegativePrompt || "",
        generationPresetId: $("generationPresetId").value.trim(),
      },
    };
  }

  async function loadCharacters() {
    state.characters = await window.AdminApi.listCharacters();
    fillSelect($("characterSelect"), state.characters, "character");
    if (state.characters.length) {
      $("characterSelect").value = state.characters[0].character.id;
      fillCharacterForm(state.characters[0]);
    }
    show($("characterResult"), { loaded: state.characters.length });
  }

  async function loadSystemHealth() {
    try {
      const llm = await window.AdminApi.llmHealth();
      setHealth("llm", llm, true);
    } catch (error) {
      setHealth("llm", { baseUrl: "LLM health failed" }, false);
    }
    try {
      const comfy = await window.AdminApi.comfyuiHealth();
      setHealth("comfy", comfy, true);
    } catch (error) {
      setHealth("comfy", { baseUrl: "ComfyUI health failed" }, false);
    }
  }

  async function loadPresets() {
    state.presets = await window.AdminApi.listGenerationPresets();
    fillSelect($("presetSelect"), state.presets, "preset");
    if (state.presets.length) {
      $("presetSelect").value = state.presets[0].id;
      fillPresetForm(state.presets[0]);
    }
    if (!$("generationPresetId").value && state.presets[0]) $("generationPresetId").value = state.presets[0].id;
    show($("presetResult"), { loaded: state.presets.length });
  }

  function fillPresetForm(preset) {
    state.selectedPreset = preset;
    $("presetName").value = preset?.name || "New preset";
    $("checkpoint").value = preset?.checkpoint || "mock_model.safetensors";
    $("width").value = preset?.width || 768;
    $("height").value = preset?.height || 1024;
    $("steps").value = preset?.steps || 24;
    $("cfg").value = preset?.cfg || 7;
    $("sampler").value = preset?.sampler || "euler";
    $("scheduler").value = preset?.scheduler || "normal";
    $("seedMode").value = preset?.seedMode || "random";
    $("workflowTemplateIdForPreset").value = preset?.workflowTemplateId || state.workflows[0]?.id || "";
    $("loras").value = JSON.stringify(preset?.loras || [], null, 2);
    $("positivePromptPrefix").value = preset?.positivePromptPrefix || "";
    $("positivePromptSuffix").value = preset?.positivePromptSuffix || "";
    $("negativePrompt").value = preset?.negativePrompt || "";
  }

  function newPresetForm() {
    state.selectedPreset = null;
    $("presetSelect").value = "";
    fillPresetForm(null);
  }

  function presetPayload() {
    return {
      name: $("presetName").value.trim() || "New preset",
      workflowTemplateId: $("workflowTemplateIdForPreset").value.trim(),
      checkpoint: $("checkpoint").value.trim() || "mock_model.safetensors",
      loras: parseJsonField("loras", []),
      width: Number($("width").value || 768),
      height: Number($("height").value || 1024),
      steps: Number($("steps").value || 24),
      cfg: Number($("cfg").value || 7),
      sampler: $("sampler").value.trim() || "euler",
      scheduler: $("scheduler").value.trim() || null,
      seedMode: $("seedMode").value.trim() || "random",
      positivePromptPrefix: $("positivePromptPrefix").value.trim() || null,
      positivePromptSuffix: $("positivePromptSuffix").value.trim() || null,
      negativePrompt: $("negativePrompt").value.trim() || null,
    };
  }

  async function loadWorkflows() {
    state.workflows = await window.AdminApi.listWorkflowTemplates();
    fillSelect($("workflowSelect"), state.workflows, "workflow");
    if (state.workflows.length) {
      $("workflowSelect").value = state.workflows[0].id;
      fillWorkflowForm(state.workflows[0]);
    }
    if (!$("workflowTemplateIdForPreset").value && state.workflows[0]) $("workflowTemplateIdForPreset").value = state.workflows[0].id;
    show($("workflowResult"), { loaded: state.workflows.length });
  }

  function fillWorkflowForm(workflow) {
    state.selectedWorkflow = workflow;
    $("workflowName").value = workflow?.name || "New workflow";
    $("workflowNodeMappingId").value = workflow?.nodeMappingId || state.mappings[0]?.id || "";
    $("workflowJson").value = JSON.stringify(workflow?.workflowJson || { nodes: {} }, null, 2);
    analyzeWorkflowFromField();
  }

  function newWorkflowForm() {
    state.selectedWorkflow = null;
    $("workflowSelect").value = "";
    fillWorkflowForm(null);
  }

  function workflowPayload() {
    return {
      name: $("workflowName").value.trim() || "New workflow",
      workflowJson: parseJsonField("workflowJson", {}),
      nodeMappingId: $("workflowNodeMappingId").value.trim() || null,
    };
  }

  function upsertWorkflow(workflow) {
    if (!workflow?.id) return;
    const index = state.workflows.findIndex((item) => item.id === workflow.id);
    if (index >= 0) state.workflows[index] = workflow;
    else state.workflows.unshift(workflow);
    fillSelect($("workflowSelect"), state.workflows, "workflow");
    $("workflowSelect").value = workflow.id;
    state.selectedWorkflow = workflow;
    if (workflow.nodeMappingId) $("workflowNodeMappingId").value = workflow.nodeMappingId;
    if (workflow.name) $("workflowName").value = workflow.name;
    if (!$("workflowTemplateIdForPreset").value) $("workflowTemplateIdForPreset").value = workflow.id;
  }

  async function loadMappings() {
    state.mappings = await window.AdminApi.listNodeMappings();
    fillSelect($("mappingSelect"), state.mappings, "mapping");
    if (state.mappings.length) {
      $("mappingSelect").value = state.mappings[0].id;
      fillMappingForm(state.mappings[0]);
    }
    if (!$("workflowNodeMappingId").value && state.mappings[0]) $("workflowNodeMappingId").value = state.mappings[0].id;
    show($("mappingResult"), { loaded: state.mappings.length });
  }

  function fillMappingForm(mapping) {
    state.selectedMapping = mapping;
    $("mappingName").value = mapping?.name || "New mapping";
    $("mappingsJson").value = JSON.stringify(
      mapping?.mappings || { positivePrompt: { nodeId: "6", inputPath: "inputs.text" } },
      null,
      2
    );
  }

  function newMappingForm() {
    state.selectedMapping = null;
    $("mappingSelect").value = "";
    fillMappingForm(null);
  }

  function mappingPayload() {
    return {
      name: $("mappingName").value.trim() || "New mapping",
      mappings: parseJsonField("mappingsJson", {}),
    };
  }

  async function run(action, target) {
    try {
      const data = await action();
      show(target, data, true);
      return data;
    } catch (error) {
      show(target, { error: error.message }, false);
      return null;
    }
  }

  async function runButton(button, action, target, labels) {
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = labels.loading;
    show(target, labels.loading);
    toast(labels.loading);
    try {
      const data = await action();
      show(target, data, true);
      toast(labels.success, true);
      return data;
    } catch (error) {
      show(target, { error: error.message }, false);
      toast(`${labels.failed}: ${error.message}`, false);
      return null;
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  async function waitForImageTask(taskId, attempts = 120) {
    let latest = null;
    for (let index = 0; index < attempts; index += 1) {
      latest = await window.ChatApi.getImageTask(taskId);
      if (latest.status === "succeeded" || latest.status === "failed") return latest;
      await new Promise((resolve) => window.setTimeout(resolve, 2000));
    }
    return latest;
  }

  function bindEvents() {
    document.querySelectorAll("[data-section-target]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        const target = document.getElementById(link.dataset.sectionTarget);
        if (!target) return;
        document.querySelectorAll("[data-section-target]").forEach((item) => item.classList.remove("is-active"));
        link.classList.add("is-active");
        target.scrollIntoView({ behavior: "smooth", block: "start" });
        window.history.replaceState(null, "", `#${link.dataset.sectionTarget}`);
      });
    });

    $("refreshCharacters").onclick = () => run(loadCharacters, $("characterResult"));
    $("refreshPresets").onclick = () => run(loadPresets, $("presetResult"));
    $("refreshWorkflows").onclick = () => run(loadWorkflows, $("workflowResult"));
    $("refreshMappings").onclick = () => run(loadMappings, $("mappingResult"));
    $("newCharacter").onclick = newCharacterForm;
    $("newPreset").onclick = newPresetForm;
    $("newWorkflow").onclick = newWorkflowForm;
    $("newMapping").onclick = newMappingForm;
    $("refreshSystemHealth").onclick = loadSystemHealth;
    $("analyzeWorkflow").onclick = analyzeWorkflowFromField;
    $("applyGuessedMapping").onclick = () => {
      const workflow = analyzeWorkflowFromField();
      if (!workflow || !state.guessedMapping) return;
      $("mappingsJson").value = JSON.stringify(state.guessedMapping, null, 2);
      if (!$("mappingName").value) $("mappingName").value = "Generated mapping";
      show($("mappingResult"), { appliedGuess: state.guessedMapping });
    };
    let workflowAnalyzeTimer = null;
    $("workflowJson").addEventListener("input", () => {
      window.clearTimeout(workflowAnalyzeTimer);
      workflowAnalyzeTimer = window.setTimeout(analyzeWorkflowFromField, 500);
    });

    $("characterSelect").onchange = () => {
      const id = $("characterSelect").value;
      const bundle = state.characters.find((item) => item.character.id === id);
      if (bundle) fillCharacterForm(bundle);
      else newCharacterForm();
    };

    $("presetSelect").onchange = () => {
      const preset = state.presets.find((item) => item.id === $("presetSelect").value);
      if (preset) fillPresetForm(preset);
      else newPresetForm();
    };
    $("workflowSelect").onchange = () => {
      const workflow = state.workflows.find((item) => item.id === $("workflowSelect").value);
      if (workflow) fillWorkflowForm(workflow);
      else newWorkflowForm();
    };
    $("mappingSelect").onchange = () => {
      const mapping = state.mappings.find((item) => item.id === $("mappingSelect").value);
      if (mapping) fillMappingForm(mapping);
      else newMappingForm();
    };

    $("saveCharacter").onclick = () =>
      run(async () => {
        const id = currentCharacterId();
        const data = id
          ? await window.AdminApi.updateCharacter(id, characterPayload())
          : await window.AdminApi.createCharacter(characterPayload());
        await loadCharacters();
        return data;
      }, $("characterResult"));

    $("publishCharacter").onclick = () =>
      run(() => window.AdminApi.publishCharacter(currentCharacterId()), $("characterResult"));

    $("generateCard").onclick = () =>
      run(async () => {
        state.generatedCard = await window.AdminApi.generateCard($("seedText").value.trim());
        return state.generatedCard;
      }, $("cardResult"));

    $("applyGeneratedCard").onclick = () => {
      if (!state.generatedCard) return show($("cardResult"), "No generated card yet.", false);
      $("characterName").value = state.generatedCard.profile?.name || $("characterName").value;
      $("description").value = state.generatedCard.profile?.description || $("description").value;
      $("systemPrompt").value = state.generatedCard.prompt?.systemPrompt || $("systemPrompt").value;
      $("characterPrompt").value = state.generatedCard.prompt?.roleplayPrompt || $("characterPrompt").value;
      $("visualPrompt").value = state.generatedCard.visual?.visualPrompt || $("visualPrompt").value;
      show($("cardResult"), { applied: true, draft: state.generatedCard });
    };

    $("savePreset").onclick = () =>
      run(async () => {
        const id = $("presetSelect").value;
        const data = id
          ? await window.AdminApi.updateGenerationPreset(id, presetPayload())
          : await window.AdminApi.createGenerationPreset(presetPayload());
        await loadPresets();
        return data;
      }, $("presetResult"));

    $("saveWorkflow").onclick = () =>
      runButton($("saveWorkflow"), async () => {
        const id = $("workflowSelect").value;
        const payload = workflowPayload();
        const data = id
          ? await window.AdminApi.updateWorkflowTemplate(id, payload)
          : await window.AdminApi.createWorkflowTemplate(payload);
        upsertWorkflow(data);
        return {
          saved: true,
          id: data.id,
          name: data.name,
          nodeMappingId: data.nodeMappingId,
          status: data.status,
          version: data.version,
        };
      }, $("workflowResult"), {
        loading: "\u6b63\u5728\u4fdd\u5b58 Workflow...",
        success: "Workflow \u5df2\u4fdd\u5b58",
        failed: "Workflow \u4fdd\u5b58\u5931\u8d25",
      });

    $("validateWorkflow").onclick = () =>
      run(() => window.AdminApi.validateWorkflowTemplate($("workflowSelect").value), $("workflowResult"));

    $("saveMapping").onclick = () =>
      run(async () => {
        const id = $("mappingSelect").value;
        const data = id
          ? await window.AdminApi.updateNodeMapping(id, mappingPayload())
          : await window.AdminApi.createNodeMapping(mappingPayload());
        await loadMappings();
        return data;
      }, $("mappingResult"));

    $("validateMapping").onclick = () =>
      run(
        () => {
          const mappingId = $("mappingSelect").value;
          if (!mappingId) throw new Error("Save NodeMapping before validation.");
          return window.AdminApi.validateNodeMapping(mappingId, {
            workflowJson: parseJsonField("workflowJson", {}),
            workflowTemplateId: $("workflowSelect").value || null,
          });
        },
        $("mappingResult")
      );

    $("testChat").onclick = () =>
      run(() => window.AdminApi.testChat(currentCharacterId(), $("testMessage").value.trim()), $("testChatResult"));

    $("testImage").onclick = () =>
      run(async () => {
        $("testImagePreview").innerHTML = "";
        const task = await window.AdminApi.testImage(currentCharacterId(), $("testImagePrompt").value.trim());
        const done = await waitForImageTask(task.id);
        if (done.generatedAsset?.publicUrl) {
          $("testImagePreview").innerHTML = `<img src="${done.generatedAsset.publicUrl}" alt="mock image" />`;
        }
        return done;
      }, $("testImageResult"));
  }

  async function init() {
    bindEvents();
    await run(async () => {
      await loadSystemHealth();
      await loadMappings();
      await loadWorkflows();
      await loadPresets();
      await loadCharacters();
      return { ready: true };
    }, $("characterResult"));
  }

  init();
})();
