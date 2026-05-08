const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const error = document.getElementById("todo-error");
const count = document.getElementById("todo-count");
const emptyState = document.getElementById("empty-state");

const MAX_TASK_LENGTH = 120;
const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F]/g;

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
  removeButton.textContent = "Remove";
  removeButton.setAttribute("aria-label", `Remove ${task}`);

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
});

input.addEventListener("input", function () {
  if (error.textContent) {
    setError("");
  }
});

updateListState();
