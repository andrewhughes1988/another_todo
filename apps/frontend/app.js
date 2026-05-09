const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const error = document.getElementById("todo-error");
const count = document.getElementById("todo-count");
const emptyState = document.getElementById("empty-state");
const themeToggle = document.getElementById("theme-toggle");
const authForm = document.getElementById("auth-form");
const emailInput = document.getElementById("email-input");
const passwordInput = document.getElementById("password-input");
const authStatus = document.getElementById("auth-status");
const authError = document.getElementById("auth-error");
const loginButton = document.getElementById("login-button");
const registerButton = document.getElementById("register-button");
const logoutButton = document.getElementById("logout-button");
const authModal = document.getElementById("auth-modal");
const authModalTitle = document.getElementById("auth-modal-title");
const authCloseButton = document.getElementById("auth-close-button");
const authSubmitButton = document.getElementById("auth-submit-button");
const authSwitchCopy = document.getElementById("auth-switch-copy");
const authSwitchButton = document.getElementById("auth-switch-button");
const filterButtons = document.querySelectorAll("[data-filter]");
const clearCompletedButton = document.getElementById("clear-completed-button");
const sessionNotice = document.getElementById("session-notice");
const addTaskButton = form.querySelector("button");

const API_CONFIG = window.APP_CONFIG || {};
const TODO_API_URL = API_CONFIG.todoApiUrl || "http://localhost:4001";
const USER_API_URL = API_CONFIG.userApiUrl || "http://localhost:4002";
const MAX_TASK_LENGTH = 240;
const HIDDEN_FORMATTING_CHARACTERS = /[\u0000-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2060-\u206F\uFEFF]/g;
const THEME_STORAGE_KEY = "todo-theme";
const AUTH_STORAGE_KEY = "todo-auth";
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

let auth = getStoredAuth();
let authMode = "login";
let isAuthenticating = false;
let isAddingTask = false;
let isLoadingTodos = false;
let todoLoadError = "";
let lastFocusedElement = null;
let currentFilter = "all";
let noticeTimer = null;

function cleanTask(value) {
  return value
    .normalize("NFKC")
    .replace(HIDDEN_FORMATTING_CHARACTERS, "")
    .replace(/\s+/g, " ")
    .trim();
}

function setTodoError(message) {
  error.textContent = message;
  input.setAttribute("aria-invalid", message ? "true" : "false");
}

function setAuthError(message) {
  authError.textContent = message;
  emailInput.setAttribute("aria-invalid", message ? "true" : "false");
  passwordInput.setAttribute("aria-invalid", message ? "true" : "false");
}

function showSessionNotice(message) {
  window.clearTimeout(noticeTimer);
  sessionNotice.textContent = message;
  sessionNotice.hidden = false;

  noticeTimer = window.setTimeout(function () {
    sessionNotice.hidden = true;
    sessionNotice.textContent = "";
  }, 3200);
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

function getStoredAuth() {
  try {
    const stored = sessionStorage.getItem(AUTH_STORAGE_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch (error) {
    return null;
  }
}

function saveAuth(nextAuth) {
  auth = nextAuth;

  try {
    if (nextAuth) {
      sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(nextAuth));
    } else {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
    }
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

function updateAuthState() {
  const signedIn = Boolean(auth && auth.accessToken);

  authStatus.textContent = signedIn ? auth.user.email : "Signed out";
  loginButton.hidden = signedIn;
  registerButton.hidden = signedIn;
  logoutButton.hidden = !signedIn;
  input.disabled = !signedIn;
  addTaskButton.disabled = !signedIn || isAddingTask;

  if (!signedIn) {
    list.replaceChildren();
  }

  updateListState();
}

function openAuthModal(mode) {
  authMode = mode;
  const isRegister = mode === "register";

  if (authModal.hidden) {
    lastFocusedElement = document.activeElement;
  }

  authModalTitle.textContent = isRegister ? "Create account" : "Sign in";
  authSubmitButton.textContent = isRegister ? "Register" : "Sign in";
  authSwitchCopy.textContent = isRegister ? "Already have an account?" : "Need an account?";
  authSwitchButton.textContent = isRegister ? "Sign in" : "Register";
  emailInput.value = "";
  passwordInput.value = "";
  setAuthError("");
  authModal.hidden = false;
  emailInput.focus();
}

function closeAuthModal() {
  authModal.hidden = true;
  setAuthError("");

  if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
    lastFocusedElement.focus();
  }
}

function getFocusableModalElements() {
  return Array.from(
    authModal.querySelectorAll('button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])')
  ).filter(function (element) {
    return !element.disabled && element.offsetParent !== null;
  });
}

function trapModalFocus(event) {
  const focusableElements = getFocusableModalElements();

  if (focusableElements.length === 0) {
    return;
  }

  const firstElement = focusableElements[0];
  const lastElement = focusableElements[focusableElements.length - 1];

  if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}

function updateListState() {
  const signedIn = Boolean(auth && auth.accessToken);
  const openTasks = list.querySelectorAll("li:not(.is-complete)").length;
  const totalTasks = list.children.length;
  const completedTasks = list.querySelectorAll("li.is-complete").length;

  count.textContent = `${openTasks} ${openTasks === 1 ? "task" : "tasks"} open`;
  clearCompletedButton.hidden = !signedIn || completedTasks === 0;

  if (!signedIn) {
    emptyState.hidden = false;
    emptyState.textContent = "Sign in to view tasks.";
    return;
  }

  if (isLoadingTodos) {
    emptyState.hidden = false;
    emptyState.textContent = "Loading tasks...";
    return;
  }

  if (todoLoadError) {
    emptyState.hidden = false;
    emptyState.textContent = todoLoadError;
    return;
  }

  const visibleTasks = list.querySelectorAll("li:not([hidden])").length;

  emptyState.hidden = visibleTasks > 0;
  emptyState.textContent = getEmptyStateMessage(totalTasks, openTasks, completedTasks);
}

function getEmptyStateMessage(totalTasks, openTasks, completedTasks) {
  if (totalTasks === 0) {
    return "No tasks yet. Add one small thing to get moving.";
  }

  if (currentFilter === "open" && openTasks === 0) {
    return "No open tasks.";
  }

  if (currentFilter === "done" && completedTasks === 0) {
    return "No completed tasks yet.";
  }

  return "No tasks match this filter.";
}

function applyTaskFilter() {
  list.querySelectorAll("li").forEach(function (item) {
    const isComplete = item.classList.contains("is-complete");
    item.hidden =
      (currentFilter === "open" && isComplete) ||
      (currentFilter === "done" && !isComplete);
  });

  filterButtons.forEach(function (button) {
    const isActive = button.dataset.filter === currentFilter;
    button.classList.toggle("is-active", isActive);
    button.setAttribute("aria-pressed", isActive ? "true" : "false");
  });
}

function createTaskItem(task) {
  const item = document.createElement("li");
  item.dataset.todoId = task.id;
  item.classList.toggle("is-complete", task.completed);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.checked = task.completed;
  checkbox.setAttribute("aria-label", `Mark ${task.title} complete`);

  const text = document.createElement("span");
  text.textContent = task.title;

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.className = "remove-task";
  removeButton.innerHTML = `
    <i data-lucide="trash-2" aria-hidden="true"></i>
    <span class="sr-only">Remove</span>
  `;
  removeButton.setAttribute("aria-label", `Remove ${task.title}`);
  removeButton.title = "Remove task";

  checkbox.addEventListener("change", async function () {
    const nextCompleted = checkbox.checked;
    const previousCompleted = !nextCompleted;

    item.classList.toggle("is-complete", nextCompleted);
    applyTaskFilter();
    updateListState();
    checkbox.disabled = true;

    try {
      const updated = await apiRequest(`${TODO_API_URL}/todos/${task.id}`, {
        method: "PATCH",
        body: JSON.stringify({ completed: nextCompleted })
      });

      task.completed = updated.completed;
      checkbox.checked = updated.completed;
      item.classList.toggle("is-complete", updated.completed);
      applyTaskFilter();
      updateListState();
    } catch (error) {
      checkbox.checked = previousCompleted;
      item.classList.toggle("is-complete", previousCompleted);
      applyTaskFilter();
      updateListState();
      setTodoError(error.message);
    } finally {
      checkbox.disabled = false;
    }
  });

  removeButton.addEventListener("click", async function () {
    const nextSibling = item.nextSibling;

    removeButton.disabled = true;
    item.remove();
    applyTaskFilter();
    updateListState();

    try {
      await apiRequest(`${TODO_API_URL}/todos/${task.id}`, { method: "DELETE" });
    } catch (error) {
      if (nextSibling && nextSibling.parentNode === list) {
        list.insertBefore(item, nextSibling);
      } else {
        list.append(item);
      }

      removeButton.disabled = false;
      applyTaskFilter();
      updateListState();
      setTodoError(error.message);
    }
  });

  item.append(checkbox, text, removeButton);
  return item;
}

function renderTodos(todos) {
  list.replaceChildren(...todos.map(createTaskItem));
  applyTaskFilter();
  updateListState();
  renderIcons();
}

async function loadTodos() {
  if (!auth || !auth.accessToken) {
    updateAuthState();
    return;
  }

  isLoadingTodos = true;
  todoLoadError = "";
  updateListState();

  try {
    const todos = await apiRequest(`${TODO_API_URL}/todos`);
    renderTodos(todos);
    setTodoError("");
  } catch (error) {
    todoLoadError = error.message;
    setTodoError(error.message);
  } finally {
    isLoadingTodos = false;
    updateListState();
  }
}

async function apiRequest(url, options = {}) {
  const headers = new Headers(options.headers || {});

  if (options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (auth && auth.accessToken) {
    headers.set("Authorization", `Bearer ${auth.accessToken}`);
  }

  const response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    saveAuth(null);
    updateAuthState();
    throw new Error("Session expired. Sign in again.");
  }

  if (!response.ok) {
    throw new Error(await getApiError(response));
  }

  if (response.status === 204) {
    return null;
  }

  return response.json();
}

async function getApiError(response) {
  try {
    const payload = await response.json();

    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch (error) {
    return "Request failed.";
  }

  return "Request failed.";
}

async function authenticate(mode) {
  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    setAuthError("Email and password are required.");
    return;
  }

  setAuthError("");
  isAuthenticating = true;
  authSubmitButton.disabled = true;
  authSubmitButton.textContent = mode === "register" ? "Registering..." : "Signing in...";

  try {
    const response = await fetch(`${USER_API_URL}/auth/${mode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password })
    });

    if (!response.ok) {
      throw new Error(await getApiError(response));
    }

    const payload = await response.json();
    saveAuth({
      accessToken: payload.access_token,
      user: payload.user
    });
    passwordInput.value = "";
    closeAuthModal();
    updateAuthState();
    showSessionNotice(mode === "register" ? "Account created. You are signed in." : "Signed in.");
    await loadTodos();
  } catch (error) {
    setAuthError(error.message);
  } finally {
    isAuthenticating = false;
    authSubmitButton.disabled = false;
    authSubmitButton.textContent = authMode === "register" ? "Register" : "Sign in";
  }
}

async function logout() {
  if (auth && auth.accessToken) {
    try {
      await fetch(`${USER_API_URL}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${auth.accessToken}` }
      });
    } catch (error) {
      // The local session can still be cleared if the network request fails.
    }
  }

  saveAuth(null);
  emailInput.value = "";
  passwordInput.value = "";
  setAuthError("");
  setTodoError("");
  updateAuthState();
  showSessionNotice("Signed out.");
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

authForm.addEventListener("submit", function (event) {
  event.preventDefault();
  authenticate(authMode);
});

loginButton.addEventListener("click", function () {
  openAuthModal("login");
});

registerButton.addEventListener("click", function () {
  openAuthModal("register");
});

authCloseButton.addEventListener("click", function () {
  closeAuthModal();
});

authSwitchButton.addEventListener("click", function () {
  openAuthModal(authMode === "register" ? "login" : "register");
});

filterButtons.forEach(function (button) {
  button.addEventListener("click", function () {
    currentFilter = button.dataset.filter;
    applyTaskFilter();
    updateListState();
  });
});

clearCompletedButton.addEventListener("click", async function () {
  const completedItems = Array.from(list.querySelectorAll("li.is-complete"));

  if (completedItems.length === 0) {
    return;
  }

  clearCompletedButton.disabled = true;
  completedItems.forEach(function (item) {
    item.remove();
  });
  applyTaskFilter();
  updateListState();

  try {
    await Promise.all(
      completedItems.map(function (item) {
        return apiRequest(`${TODO_API_URL}/todos/${item.dataset.todoId}`, { method: "DELETE" });
      })
    );
    setTodoError("");
  } catch (error) {
    setTodoError(error.message);
    await loadTodos();
  } finally {
    clearCompletedButton.disabled = false;
    updateListState();
  }
});

authModal.addEventListener("click", function (event) {
  if (event.target === authModal) {
    closeAuthModal();
  }
});

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape" && !authModal.hidden) {
    closeAuthModal();
  } else if (event.key === "Tab" && !authModal.hidden) {
    trapModalFocus(event);
  }
});

logoutButton.addEventListener("click", function () {
  logout();
});

form.addEventListener("submit", async function (event) {
  event.preventDefault();

  const task = cleanTask(input.value);

  if (!auth || !auth.accessToken) {
    setTodoError("Sign in before adding tasks.");
    return;
  }

  if (!task) {
    setTodoError("Enter a task before adding it.");
    input.focus();
    return;
  }

  if (task.length > MAX_TASK_LENGTH) {
    setTodoError(`Tasks must be ${MAX_TASK_LENGTH} characters or fewer.`);
    input.focus();
    return;
  }

  isAddingTask = true;
  addTaskButton.disabled = true;
  addTaskButton.querySelector("span").textContent = "Adding...";

  try {
    const created = await apiRequest(`${TODO_API_URL}/todos`, {
      method: "POST",
      body: JSON.stringify({ title: task })
    });

    list.prepend(createTaskItem(created));
    input.value = "";
    setTodoError("");
    applyTaskFilter();
    updateListState();
    renderIcons();
  } catch (error) {
    setTodoError(error.message);
  } finally {
    isAddingTask = false;
    addTaskButton.disabled = !auth || !auth.accessToken;
    addTaskButton.querySelector("span").textContent = "Add task";
  }
});

input.addEventListener("input", function () {
  if (error.textContent) {
    setTodoError("");
  }
});

emailInput.addEventListener("input", function () {
  if (authError.textContent) {
    setAuthError("");
  }
});

passwordInput.addEventListener("input", function () {
  if (authError.textContent) {
    setAuthError("");
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
updateAuthState();
loadTodos();
renderIcons();
