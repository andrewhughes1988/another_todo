import React from "react";
import ReactDOM from "react-dom/client";
import { CheckCircle2, Plus } from "lucide-react";
import "./styles.css";

const todoApiUrl = import.meta.env.VITE_TODO_API_URL ?? "http://localhost:4001";

function App() {
  return (
    <main className="shell">
      <section className="panel">
        <div className="heading">
          <CheckCircle2 aria-hidden="true" />
          <div>
            <h1>Todo Cloud Native</h1>
            <p>Frontend wired for the todo and user services.</p>
          </div>
        </div>

        <form className="composer">
          <input aria-label="New todo" placeholder="Add a deployment task" />
          <button type="button" aria-label="Add todo">
            <Plus aria-hidden="true" />
          </button>
        </form>

        <ul className="todos">
          <li>Split APIs by bounded context</li>
          <li>Queue notifications for async delivery</li>
          <li>Promote infrastructure through dev and prod</li>
        </ul>

        <p className="meta">Todo API: {todoApiUrl}</p>
      </section>
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

