"use strict";
const $ = (id) => document.getElementById(id);
let project = null;
let pending = false;
let signature = "";
let serverError = false;
const circumference = 2 * Math.PI * 51;

function setError(message) {
  $("error").textContent = message;
  $("error").hidden = !message;
}

function setConnected(connected) {
  $("connection").textContent = connected ? "Saved locally" : "Connection lost";
  $("connection").classList.toggle("offline", !connected);
}

function panelOpen(open) {
  document.querySelector("main").classList.toggle("is-open", open);
  $("progress-panel").hidden = !open;
  $("pet").setAttribute("aria-expanded", String(open));
  $("pet").setAttribute("aria-label", `Motchi: ${open ? "hide" : "show"} project progress`);
  $("click-hint").hidden = open;
}
$("pet").addEventListener("click", () => panelOpen($("progress-panel").hidden));
$("close-panel").addEventListener("click", () => {
  panelOpen(false);
  $("pet").focus();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("progress-panel").hidden) {
    panelOpen(false);
    $("pet").focus();
  }
});

function setBusy(busy) {
  pending = busy;
  document.querySelectorAll("form button, form input, .task input").forEach(el => {
    el.disabled = busy;
  });
}

function render(next) {
  if (project && next.revision < project.revision) return;
  project = next;
  $("project-label").textContent = next.name;
  if (document.activeElement !== $("project-name")) $("project-name").value = next.name;
  $("percent").replaceChildren(document.createTextNode(String(next.percent)), Object.assign(document.createElement("span"), {textContent: "%"}));
  $("ring-fill").style.strokeDasharray = String(circumference);
  $("ring-fill").style.strokeDashoffset = String(circumference * (1 - next.percent / 100));
  $("ring").setAttribute("aria-valuenow", String(next.percent));
  $("ring").setAttribute("aria-valuetext", next.total ? `${next.completed} of ${next.total} tasks complete, ${next.percent} percent` : "No tasks yet");
  $("task-count").textContent = next.total ? `${next.completed} of ${next.total} tasks complete` : "No tasks yet";
  $("remaining").textContent = next.total ? `${next.total - next.completed} to go` : "";
  $("encouragement").textContent = !next.total ? "Every project starts here." : next.completed === next.total ? "You did it. All tasks complete!" : !next.completed ? "Ready for your first step?" : next.percent >= 75 ? "The finish line is in sight." : next.percent >= 50 ? "Look how far you’ve come." : "Little steps. Real progress.";
  $("empty").hidden = next.total > 0;
  // Keep existing checkbox nodes (and keyboard focus) on unchanged polls.
  const nextSignature = JSON.stringify(next.tasks);
  if (nextSignature !== signature) {
    const focusedTask = document.activeElement?.dataset.task;
    const rows = next.tasks.map(task => {
      const item = document.createElement("li");
      item.className = `task${task.done ? " done" : ""}`;
      const label = document.createElement("label");
      const check = document.createElement("input");
      check.type = "checkbox";
      check.checked = task.done;
      check.dataset.task = task.id;
      const title = document.createElement("span");
      title.className = "task-title";
      title.textContent = task.title;
      check.addEventListener("change", async () => {
        const done = check.checked;
        check.checked = task.done;
        await mutate({action: "set_done", id: task.id, done});
      });
      label.append(check, title);
      item.append(label);
      return item;
    });
    $("tasks").replaceChildren(...rows);
    signature = nextSignature;
    if (focusedTask) {
      [...$("tasks").querySelectorAll("input")].find(el => el.dataset.task === focusedTask)?.focus();
    }
  }
}

async function fetchState() {
  const response = await fetch("/api/project", {signal: AbortSignal.timeout(5000)});
  const state = await response.json();
  if (!response.ok) throw new Error(state.error || "Could not read the project");
  return state;
}

async function refresh() {
  if (pending) return;
  try {
    const state = await fetchState();
    if (pending) return;
    render(state);
    setConnected(true);
    if (serverError) { setError(""); serverError = false; }
  } catch (error) {
    setConnected(false);
    serverError = true;
    setError(`${error.message}. Check that the local Progress Dog server is running.`);
  }
}

async function mutate(action) {
  if (pending || !project) return false;
  const focusedTask = document.activeElement?.dataset.task;
  setBusy(true);
  setError("");
  try {
    const response = await fetch("/api/project", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({...action, revision: project.revision}),
      signal: AbortSignal.timeout(5000)
    });
    const next = await response.json();
    if (!response.ok) {
      if (response.status === 409) render(await fetchState());
      throw new Error(next.error || "Could not save your change");
    }
    render(next);
    setConnected(true);
    serverError = false;
    return true;
  } catch (error) {
    setError(error.message);
    return false;
  } finally {
    setBusy(false);
    if (focusedTask) {
      [...$("tasks").querySelectorAll("input")].find(el => el.dataset.task === focusedTask)?.focus();
    }
  }
}

$("add-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const title = $("task-title").value.trim();
  if (!title) { $("task-title").focus(); return; }
  if (await mutate({action: "add", title})) {
    $("task-title").value = "";
    $("task-title").focus();
  }
});
$("name-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const name = $("project-name").value.trim();
  if (name && await mutate({action: "rename", name})) document.querySelector(".settings").open = false;
});
refresh();
setInterval(refresh, 2000);
