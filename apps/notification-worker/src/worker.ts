import Redis from "ioredis";
import pino from "pino";

const logger = pino({ name: "notification-worker" });
const redisUrl = process.env.REDIS_URL ?? "redis://localhost:6379";
const redis = new Redis(redisUrl);

async function start() {
  logger.info({ redisUrl }, "notification worker started");

  redis.on("error", (error) => {
    logger.error({ error }, "redis connection error");
  });

  setInterval(() => {
    logger.info("waiting for notification jobs");
  }, 30000);
}

start().catch((error) => {
  logger.error({ error }, "notification worker crashed");
  process.exit(1);
});

