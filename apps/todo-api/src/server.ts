import cors from "cors";
import express from "express";
import helmet from "helmet";
import { z } from "zod";

const port = Number(process.env.PORT ?? 4001);
const app = express();

const createTodoSchema = z.object({
  title: z.string().min(1).max(200),
  userId: z.string().min(1)
});

const todos = [
  { id: "todo_1", userId: "user_1", title: "Create service boundaries", completed: true },
  { id: "todo_2", userId: "user_1", title: "Wire async notifications", completed: false }
];

app.use(helmet());
app.use(cors());
app.use(express.json());

app.get("/health", (_request, response) => {
  response.json({ ok: true, service: "todo-api" });
});

app.get("/todos", (_request, response) => {
  response.json({ data: todos });
});

app.post("/todos", (request, response) => {
  const parsed = createTodoSchema.safeParse(request.body);

  if (!parsed.success) {
    response.status(400).json({ error: parsed.error.flatten() });
    return;
  }

  const todo = {
    id: `todo_${todos.length + 1}`,
    userId: parsed.data.userId,
    title: parsed.data.title,
    completed: false
  };

  todos.push(todo);
  response.status(201).json({ data: todo });
});

app.listen(port, () => {
  console.log(`todo-api listening on ${port}`);
});

