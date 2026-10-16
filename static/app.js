const byId = (id) => document.getElementById(id);
const toast = byId("toast");
let toastTimer;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  let data = {};
  try {
    data = await response.json();
  } catch (_error) {
    data = {};
  }
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
  return data;
}

function notify(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("is-error", isError);
  toast.classList.add("is-visible");
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => toast.classList.remove("is-visible"), 3200);
}

function showView(name) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    const active = button.dataset.view === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  document.querySelectorAll(".view-panel").forEach((panel) => {
    const active = panel.id === `view-${name}`;
    panel.hidden = !active;
    panel.classList.toggle("is-visible", active);
  });
  if (name === "tasks") loadTasks();
  if (name === "memories") loadMemories();
}

function setEmpty(list, message) {
  const item = document.createElement("li");
  item.className = "empty-state";
  item.textContent = message;
  list.replaceChildren(item);
}

function renderTasks(tasks) {
  const openCount = tasks.filter((task) => !task.completed).length;
  byId("openTaskCount").textContent = openCount;
  byId("taskListCount").textContent = `${tasks.length} ${tasks.length === 1 ? "item" : "items"}`;
  const list = byId("taskList");
  if (!tasks.length) return setEmpty(list, "Nothing on the list yet. Add a task when you're ready.");

  list.replaceChildren(...tasks.map((task) => {
    const row = document.createElement("li");
    row.className = `record-row${task.completed ? " is-complete" : ""}`;
    const main = document.createElement("div");
    main.className = "record-main";
    const title = document.createElement("span");
    title.className = "record-title";
    title.textContent = task.title;
    const meta = document.createElement("div");
    meta.className = "record-meta";
    const priority = document.createElement("span");
    priority.className = `priority-tag${task.priority === "high" ? " is-high" : ""}`;
    priority.textContent = `${task.priority} priority`;
    meta.append(priority);
    if (task.due_date) {
      const due = document.createElement("span");
      due.textContent = `Due ${task.due_date}`;
      meta.append(due);
    }
    main.append(title, meta);
    row.append(main);
    const button = document.createElement("button");
    button.className = "record-action";
    button.type = "button";
    button.textContent = task.completed ? "Completed" : "Mark done";
    button.disabled = Boolean(task.completed);
    button.setAttribute("aria-label", `${button.textContent}: ${task.title}`);
    if (!task.completed) button.addEventListener("click", () => finishTask(task.id));
    row.append(button);
    return row;
  }));
}

async function loadTasks() {
  try {
    const data = await api("/api/tasks");
    renderTasks(data.tasks);
  } catch (error) {
    notify(error.message, true);
  }
}

async function finishTask(id) {
  try {
    const data = await api(`/api/tasks/${id}`, { method: "PATCH" });
    renderTasks(data.tasks);
    notify("Task completed.");
  } catch (error) {
    notify(error.message, true);
  }
}

function renderMemories(memories) {
  byId("memoryCount").textContent = memories.length;
  byId("memoryListCount").textContent = `${memories.length} ${memories.length === 1 ? "item" : "items"}`;
  const list = byId("memoryList");
  if (!memories.length) return setEmpty(list, "No saved memories found.");

  list.replaceChildren(...memories.map((memory) => {
    const row = document.createElement("li");
    row.className = "record-row";
    const main = document.createElement("div");
    main.className = "record-main";
    const content = document.createElement("span");
    content.className = "record-title";
    content.textContent = memory.content;
    main.append(content);
    const remove = document.createElement("button");
    remove.className = "record-action";
    remove.type = "button";
    remove.textContent = "Delete";
    remove.setAttribute("aria-label", `Delete memory ${memory.id}`);
    remove.addEventListener("click", () => removeMemory(memory.id));
    row.append(main, remove);
    return row;
  }));
}

async function loadMemories(query = "") {
  try {
    const suffix = query ? `?q=${encodeURIComponent(query)}` : "";
    const data = await api(`/api/memories${suffix}`);
    renderMemories(data.memories);
  } catch (error) {
    notify(error.message, true);
  }
}

async function removeMemory(id) {
  try {
    const data = await api(`/api/memories/${id}`, { method: "DELETE" });
    renderMemories(data.memories);
    notify("Memory deleted.");
  } catch (error) {
    notify(error.message, true);
  }
}

function addMessage(text, role, pending = false) {
  const message = document.createElement("article");
  message.className = `message ${role === "user" ? "user-message" : "assistant-message"}`;
  if (pending) message.dataset.pending = "true";
  const mark = document.createElement("div");
  mark.className = "message-mark";
  mark.setAttribute("aria-hidden", "true");
  mark.textContent = role === "user" ? "Y" : "S";
  const body = document.createElement("div");
  body.className = "message-body";
  const meta = document.createElement("div");
  meta.className = "message-meta";
  meta.textContent = role === "user" ? "YOU" : "STILLROOM";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  body.append(meta, paragraph);
  message.append(mark, body);
  byId("conversation").append(message);
  message.scrollIntoView({ block: "nearest", behavior: "smooth" });
  return message;
}

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});
document.querySelectorAll("[data-open-view]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.openView));
});

byId("chatForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = byId("chatInput");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  addMessage(message, "user");
  const pending = addMessage("Thinking...", "assistant", true);
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  try {
    const data = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
    pending.querySelector("p").textContent = data.answer;
  } catch (error) {
    pending.querySelector("p").textContent = error.message;
    pending.classList.add("is-error");
  } finally {
    pending.removeAttribute("data-pending");
    button.disabled = false;
    input.focus();
  }
});

byId("chatInput").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    byId("chatForm").requestSubmit();
  }
});

byId("taskForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const values = new FormData(form);
  try {
    const data = await api("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: values.get("title"),
        due_date: values.get("due_date") || null,
        priority: values.get("priority"),
      }),
    });
    renderTasks(data.tasks);
    form.reset();
    byId("taskPriority").value = "medium";
    byId("taskFeedback").textContent = "Task added.";
  } catch (error) {
    byId("taskFeedback").textContent = error.message;
  }
});

byId("memoryForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const content = byId("memoryContent").value;
  try {
    const data = await api("/api/memories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    renderMemories(data.memories);
    event.currentTarget.reset();
    notify("Memory saved.");
  } catch (error) {
    notify(error.message, true);
  }
});

byId("memorySearchForm").addEventListener("submit", (event) => {
  event.preventDefault();
  loadMemories(byId("memorySearch").value.trim());
});
byId("clearMemorySearch").addEventListener("click", () => {
  byId("memorySearch").value = "";
  loadMemories();
});

byId("documentFile").addEventListener("change", (event) => {
  byId("fileName").textContent = event.currentTarget.files[0]?.name || "Choose a TXT or Markdown file";
});
byId("documentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const result = byId("summaryResult");
  const button = event.currentTarget.querySelector("button[type=submit]");
  button.disabled = true;
  button.textContent = "Summarizing...";
  result.hidden = false;
  result.textContent = "Working with your local model...";
  try {
    const data = await api("/api/summarize", { method: "POST", body: new FormData(event.currentTarget) });
    result.textContent = data.summary;
  } catch (error) {
    result.textContent = error.message;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Summarize <span aria-hidden="true">↗</span>';
  }
});

const today = new Date();
byId("todayLabel").textContent = new Intl.DateTimeFormat(undefined, { weekday: "long", month: "long", day: "numeric" }).format(today);
api("/api/status").then((data) => {
  const online = data.ollama_available;
  byId("connectionText").textContent = online ? `${data.model} is ready` : "Ollama is offline";
  byId("connectionPill").querySelector(".status-dot").classList.toggle(online ? "is-online" : "is-offline", true);
  byId("sidebarStatusText").textContent = online ? "Model connected" : "Model offline";
  byId("sidebarStatusDot").classList.toggle(online ? "is-online" : "is-offline", true);
}).catch(() => {
  byId("connectionText").textContent = "Model status unavailable";
  byId("sidebarStatusText").textContent = "Status unavailable";
});
loadTasks();
loadMemories();