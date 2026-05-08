const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const error = document.getElementById("todo-error");
const count = document.getElementById("todo-count");
const emptyState = document.getElementById("empty-state");
const themeToggle = document.getElementById("theme-toggle");

const MAX_TASK_LENGTH = 120;
const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F]/g;
const THEME_STORAGE_KEY = "todo-theme";

function cleanTask(value) {
  return value
    .normalize("NFKC")
    .replace(CONTROL_CHARACTERS, "")
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
  const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
  return storedTheme === "dark" || storedTheme === "light" ? storedTheme : null;
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
  if (window.lucide) {
    window.lucide.createIcons({
      attrs: {
        "stroke-width": 2.25
      }
    });
  }
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

  localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
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
