# The stack

`madmp-dsw` is a Data Stewardship Wizard 4.31 deployment, plus the maDMP
submission webhook running beside it. Seven files, of which one is a
`docker-compose.yml` and one is a `.env`.

It is a **declarative deployment**. It builds nothing: every image it runs is
pulled, including the webhook, which is built and published by
[madmp-core](../core/12-engineering.md).

## Six services

| Service | Port | What it is |
|---|---|---|
| `server` | `127.0.0.1:3000` | the DSW API |
| `client` | `127.0.0.1:8080` | the web interface |
| `docworker` | none | renders documents |
| `postgres` | none | the database |
| `minio` | `127.0.0.1:9000`, `9001` | object storage, and its console |
| `submission` | none | the maDMP webhook |

Plus `createbucket`, a one-shot task under `profiles: [tools]`, and a `mailer`
that is commented out.

```mermaid
flowchart TB
    browser["a browser"] -->|8080| client
    browser -->|"3000, the API<br/>directly"| server
    browser -->|"9000, presigned<br/>download URLs"| minio
    client
    server --> postgres
    server --> minio
    docworker --> postgres
    docworker --> minio
    docworker -->|"waits for a healthy API"| server
    server -->|"submission:8080<br/>on the compose network"| submission
    submission -->|"a commit"| gh["GitHub<br/>madmp-registry"]
```

## Everything is bound to 127.0.0.1

```yaml
ports:
  - 127.0.0.1:3000:3000
```

Not `3000:3000`. Reaching this stack from another machine goes through a proxy,
**not by widening the binding**. Two consequences worth knowing before you
deploy it:

- a GitHub runner cannot reach it, which is why the `publish` job in madmp-core
  is conditional and a local stack is published to by hand
- `9000` has to stay published even so, because the browser fetches rendered
  documents from MinIO directly through a presigned URL

`9001` is MinIO's own admin console, kept for local inspection and not meant to
be forwarded.

## The shared config block

`server` and `docworker` take the same DSW settings, through a YAML anchor:

```yaml
x-dsw-config: &dsw-config
  GENERAL_CLIENT_URL: ${CLIENT_URL}
  GENERAL_SECRET: ${GENERAL_SECRET}
  GENERAL_RSA_PRIVATE_KEY: ${GENERAL_RSA_PRIVATE_KEY}
  DATABASE_CONNECTION_STRING: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
  S3_URL: ${S3_URL}
  S3_USERNAME: ${MINIO_ROOT_USER}
  S3_PASSWORD: ${MINIO_ROOT_PASSWORD}
  S3_BUCKET: ${S3_BUCKET}
```

Each name is that setting's `application.yml` path in upper case, because **DSW
reads the environment before any config file**. There is no `application.yml`
in this repository at all.

!!! danger "The image carries its own application.yml underneath"
    Its defaults are not neutral: it names the database `wizard`. Set every
    value that matters rather than relying on a fallback.

!!! note "No `:-default` anywhere in the compose file"
    Default values are written in `.env.example`, and a second copy in the
    compose file would drift from it. One home per value.

## The three services with something to say

### server

Published for amd64 only upstream, so an ARM host runs it emulated. That is
declared rather than left to chance:

```yaml
platform: linux/amd64
```

Its healthcheck is the image's own test at a usable cadence. The image ships a
300 second interval with no start period, which would keep the container from
reporting healthy for five minutes however fast it answered. Here it is
10 seconds, with a 300 second `start_period` leaving room for the migrations
the first run applies. Failures inside that window do not count against
retries.

### docworker

```yaml
APPLICATION_CONFIG_PATH: /dev/null
```

The image bakes `APPLICATION_CONFIG_PATH=/app/config/application.yml`, and its
CLI checks that the path **exists** before reading any configuration. So a file
has to be there even when every setting comes from the environment. `/dev/null`
passes the check and parses as an empty document.

It waits on `server: condition: service_healthy`, so it waits for an API that
answers rather than for a container that exists.

### postgres

Not published. Nothing on the host calls it, containers reach it as
`postgres:5432`, and inspecting it goes through the Docker daemon:

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

!!! warning "pg_isready needs -h 127.0.0.1 to be honest"
    ```yaml
    test: ["CMD-SHELL", 'pg_isready -h 127.0.0.1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"']
    ```
    Without the host, `pg_isready` asks over the unix socket, which the
    temporary server `initdb` runs already answers. The check would go green
    before the database accepts a single TCP connection.

    The `$$` leave both names to the container's shell rather than letting
    compose interpolate them.

## createbucket, and why it has a profile

DSW does not create its own bucket.

```bash
docker compose run --rm createbucket
```

`profiles: [tools]` keeps it out of `docker compose up`, which would otherwise
treat a one-shot task as a service that keeps stopping and restarting.

!!! danger "The `$$` here are a secret leak away"
    The entrypoint uses `$$MINIO_ROOT_USER` and `$$MINIO_ROOT_PASSWORD` so that
    compose leaves them to the container's shell. With a single `$`, both
    credentials would be expanded into a command line **the host can read**.

## mailer is commented out, not deleted

It is idle while mail is disabled, and it is left in place as a comment because
of how it fails.

!!! warning "Enabling mail without it fails silently"
    The server queues mailer commands nobody processes, and the interface still
    reports the message as sent. Uncomment the service together with enabling
    mail, never one without the other.

## Two volumes

| Volume | Holds |
|---|---|
| `madmp-dsw_db-data` | the database |
| `madmp-dsw_s3-data` | rendered documents |

`docker compose down -v` destroys both, which is how a clean run starts. The
compose file pins the project name so those volumes keep their names whatever
the folder is called:

```yaml
name: madmp-dsw
```
