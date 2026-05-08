import cors from "cors";
import express from "express";
import helmet from "helmet";
import { z } from "zod";

const port = Number(process.env.PORT ?? 4002);
const app = express();

const createUserSchema = z.object({
  email: z.string().email(),
  name: z.string().min(1).max(120)
});

const users = [
  { id: "user_1", email: "demo@example.com", name: "Demo User" }
];

app.use(helmet());
app.use(cors());
app.use(express.json());

app.get("/health", (_request, response) => {
  response.json({ ok: true, service: "user-api" });
});

app.get("/users", (_request, response) => {
  response.json({ data: users });
});

app.post("/users", (request, response) => {
  const parsed = createUserSchema.safeParse(request.body);

  if (!parsed.success) {
    response.status(400).json({ error: parsed.error.flatten() });
    return;
  }

  const user = {
    id: `user_${users.length + 1}`,
    email: parsed.data.email,
    name: parsed.data.name
  };

  users.push(user);
  response.status(201).json({ data: user });
});

app.listen(port, () => {
  console.log(`user-api listening on ${port}`);
});

