const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const error = document.getElementById("todo-error");

const MAX_TASK_LENGTH = 120;
const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F]/g;

function cleanTask(value) {
  return value
    .normalize("NFKC")
    .replace(CONTROL_CHARACTERS, "")
    .replace(/\s+/g, " ")
    .trim();
}

function setError(message) {
  error.textContent = message;
  input.setAttribute("aria-invalid", message ? "true" : "false");
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

  const item = document.createElement("li");
  item.textContent = task;

  list.appendChild(item);
  input.value = "";
  setError("");
});

input.addEventListener("input", function () {
  if (error.textContent) {
    setError("");
  }
});
