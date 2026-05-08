const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const error = document.getElementById("todo-error");
const count = document.getElementById("todo-count");
const emptyState = document.getElementById("empty-state");
const themeToggle = document.getElementById("theme-toggle");

const MAX_TASK_LENGTH = 240;
const HIDDEN_FORMATTING_CHARACTERS = /[\u0000-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g;
const THEME_STORAGE_KEY = "todo-theme";
const ICONS = {
  moon: [
    ["path", { d: "M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" }]
  ],
  plus: [
    ["path", { d: "M5 12h14" }],
    ["path", { d: "M12 5v14" }]
  ],
  sun: [
    ["circle", { cx: "12", cy: "12", r: "4" }],
    ["path", { d: "M12 2v2" }],
    ["path", { d: "M12 20v2" }],
    ["path", { d: "m4.93 4.93 1.41 1.41" }],
    ["path", { d: "m17.66 17.66 1.41 1.41" }],
    ["path", { d: "M2 12h2" }],
    ["path", { d: "M20 12h2" }],
    ["path", { d: "m6.34 17.66-1.41 1.41" }],
    ["path", { d: "m19.07 4.93-1.41 1.41" }]
  ],
  "trash-2": [
    ["path", { d: "M3 6h18" }],
    ["path", { d: "M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" }],
    ["path", { d: "M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" }],
    ["path", { d: "M10 11v6" }],
    ["path", { d: "M14 11v6" }]
  ]
};

function cleanTask(value) {
  return value
    .normalize("NFKC")
    .replace(HIDDEN_FORMATTING_CHARACTERS, "")
    .replace(/\s+/g, " ")
    .trim();
}

// TODO: Reuse this validation when tasks are loaded from persistence.
function setError(message) {
  error.textContent = message;
  input.setAttribute("aria-invalid", message ? "true" : "false");
}

function getSystemTheme() {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme() {
  const storedTheme = safeGetTheme();
  return storedTheme === "dark" || storedTheme === "light" ? storedTheme : null;
}

function safeGetTheme() {
  try {
    return localStorage.getItem(THEME_STORAGE_KEY);
  } catch (error) {
    return null;
  }
}

function safeSaveTheme(theme) {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (error) {
    return;
  }
}

function setTheme(theme) {
  const isDark = theme === "dark";

  document.documentElement.dataset.theme = theme;
  themeToggle.innerHTML = `
    <i data-lucide="${isDark ? "sun" : "moon"}" aria-hidden="true"></i>
    <span>${isDark ? "Light" : "Dark"}</span>
  `;
  themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
  renderIcons();
}

function updateListState() {
  const openTasks = list.querySelectorAll("li:not(.is-complete)").length;
  const totalTasks = list.children.length;

  count.textContent = `${openTasks} ${openTasks === 1 ? "task" : "tasks"} open`;
  emptyState.hidden = totalTasks > 0;
}

function createTaskItem(task) {
  const item = document.createElement("li");

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.setAttribute("aria-label", `Mark ${task} complete`);

  const text = document.createElement("span");
  text.textContent = task;

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "remove-task";
  removeButton.innerHTML = `
    <i data-lucide="trash-2" aria-hidden="true"></i>
    <span class="sr-only">Remove</span>
  `;
  removeButton.setAttribute("aria-label", `Remove ${task}`);
  removeButton.title = "Remove task";

  checkbox.addEventListener("change", function () {
    item.classList.toggle("is-complete", checkbox.checked);
    updateListState();
  });

  removeButton.addEventListener("click", function () {
    item.remove();
    updateListState();
  });

  item.append(checkbox, text, removeButton);
  return item;
}

function renderIcons() {
  document.querySelectorAll("[data-lucide]").forEach(function (placeholder) {
    const iconName = placeholder.dataset.lucide;
    const icon = ICONS[iconName];

    if (!icon || placeholder.tagName.toLowerCase() === "svg") {
      return;
    }

    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2.25");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.dataset.lucide = iconName;

    icon.forEach(function ([tagName, attrs]) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", tagName);

      Object.entries(attrs).forEach(function ([name, value]) {
        node.setAttribute(name, value);
      });

      svg.appendChild(node);
    });

    placeholder.replaceWith(svg);
  });
}

form.addEventListener("submit", function (event) {
  event.preventDefault();

  const task = cleanTask(input.value);

  if (!task) {
    setError("Enter a task before adding it.");
    input.focus();
    return;
  }

  if (task.length > MAX_TASK_LENGTH) {
    setError(`Tasks must be ${MAX_TASK_LENGTH} characters or fewer.`);
    input.focus();
    return;
  }

  const item = createTaskItem(task);

  list.appendChild(item);
  input.value = "";
  setError("");
  updateListState();
  renderIcons();
});

input.addEventListener("input", function () {
  if (error.textContent) {
    setError("");
  }
});

themeToggle.addEventListener("click", function () {
  const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";

  safeSaveTheme(nextTheme);
  setTheme(nextTheme);
});

window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () {
  if (!getStoredTheme()) {
    setTheme(getSystemTheme());
  }
});

setTheme(getStoredTheme() || getSystemTheme());
updateListState();
renderIcons();
