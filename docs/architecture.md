# Architecture

The application is organized as a small service-oriented system:

- `frontend` provides the user interface.
- `todo-api` owns todo list behavior and persistence.
- `user-api` owns user profiles and identity-adjacent data.
- `notification-worker` processes asynchronous notification jobs.
- `postgres` stores durable application data for local development.
- `redis` provides a local queue/cache primitive for worker development.

In production, the APIs and worker can be deployed independently behind a managed ingress or API gateway. The Terraform folders are split by environment so dev and prod state can remain isolated.

