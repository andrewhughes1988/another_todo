const form = document.getElementById("todo-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");

form.addEventListener("submit", function (event) {
  event.preventDefault();

  const task = input.value.trim();

  if (!task) {
    return;
  }

  const item = document.createElement("li");
  item.textContent = task;

  list.appendChild(item);
  input.value = "";
});