# Configuration

One file, `.env`, read by docker compose and by nothing else. There is no
`application.yml` in this repository: DSW reads the environment before any
config file, so the environment is the whole of the configuration.

```bash
cp .env.example .env
```

The values that already carry one work as they stand. The empty ones have no
default, and each is described where it sits in the file.

## The nineteen values

| Block | Variable | Secret | Default |
|---|---|---|---|
| DSW | `DSW_VERSION` | | `4.31` |
| | `GENERAL_SECRET` | ● | |
| | `GENERAL_RSA_PRIVATE_KEY` | ● | |
| Database | `POSTGRES_VERSION` | | `17.5` |
| | `POSTGRES_DB` | | `engine-wizard` |
| | `POSTGRES_USER` | | `postgres` |
| | `POSTGRES_PASSWORD` | ● | |
| Object storage | `MINIO_VERSION` | | a release tag |
| | `MC_VERSION` | | a release tag |
| | `MINIO_ROOT_USER` | | `minio` |
| | `MINIO_ROOT_PASSWORD` | ● | |
| | `S3_BUCKET` | | `engine-wizard` |
| Webhook | `MADMP_CORE_VERSION` | | `v1.0.0` |
| | `SUBMISSION_TOKEN` | ● | |
| | `REGISTRY_TOKEN` | ● | |
| | `REGISTRY_OWNER` | | |
| | `REGISTRY_REPO` | | |
| URLs | `API_URL` | | localhost |
| | `CLIENT_URL` | | localhost |
| | `S3_URL` | | `host.docker.internal` |

Six secrets, and none of them has a default, an example value included.

## The two that sign tokens

```bash
openssl rand -hex 16          # GENERAL_SECRET
openssl genrsa -traditional 4096   # GENERAL_RSA_PRIVATE_KEY
```

!!! danger "Never inherit these from anywhere"
    Whoever holds them can forge a valid token against this instance. Copying
    them from an example, from another deployment, or from a colleague's
    machine defeats the point of having them.

!!! warning "Two flags that are not optional"
    `-hex 16` and not more: the secret must be **exactly 32 ASCII characters**.

    `-traditional` produces the PKCS#1 form, the one starting with
    `BEGIN RSA PRIVATE KEY`. OpenSSL 3 defaults to PKCS#8, which DSW does not
    read.

The key is the one multi-line value in the file. It goes between double quotes,
keeping its line breaks:

```
GENERAL_RSA_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
MIIJKAIBAAKC...
-----END RSA PRIVATE KEY-----"
```

A multi-line value left without its quotes is the one mistake `docker compose
config` catches and a key-by-key check does not: compose reads every following
line as a new variable.

## The database password ends up in a URI

```yaml
DATABASE_CONNECTION_STRING: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
```

!!! warning "Percent-encode what is special in a URL"
    A `@`, a `/` or a `#` in the password breaks the host name rather than
    failing loudly. `openssl rand -hex 24` avoids the question entirely.

!!! warning "Applied at the very first initdb only"
    The database and its account are created once. Changing these three values
    afterwards has **no effect** on an existing database. Starting over takes
    `docker compose down -v`, which destroys the data.

MinIO has its own constraint: it refuses a password under 8 characters, or a
username under 3.

## The three URLs

```
API_URL=http://localhost:3000/wizard-api
CLIENT_URL=http://localhost:8080/wizard
S3_URL=http://host.docker.internal:9000
```

They are the values a deployment somewhere else has to change, and each is
resolved by a different party.

| Variable | Resolved by | Must therefore be |
|---|---|---|
| `API_URL` | the **browser** | an address the user's machine resolves, never a compose service name |
| `CLIENT_URL` | the browser, and DSW when it writes links | the public address of the interface |
| `S3_URL` | the containers **and** the browser | an address both resolve |

!!! danger "S3_URL is the awkward one"
    It is both the address the containers use to reach object storage and what
    goes **inside the presigned download URLs** the browser follows. One value
    has to work from both sides. `host.docker.internal` manages that on Docker
    Desktop, and a real deployment behind a proxy needs an address that is
    genuinely reachable from both.

## The webhook's four

`MADMP_CORE_VERSION` names the madmp-core release the webhook runs, as
published under `ghcr.io/pstcricq/ostrails-madmp-core/submission`. Naming that
tag is the whole of how an operator chooses which engine and which rules judge
a submission.

The other four are required, and read **once when the webhook starts**:

| Variable | What it is |
|---|---|
| `SUBMISSION_TOKEN` | the shared secret DSW sends as `Authorization: Bearer ...` |
| `REGISTRY_TOKEN` | a fine-grained PAT, Contents RW and Metadata R on the registry |
| `REGISTRY_OWNER` | the account owning the registry |
| `REGISTRY_REPO` | the repository itself |

`SUBMISSION_TOKEN` has to be **the same value on both sides**: here, and in the
submission service DSW holds. `dsw.publish submission` is what writes it into
DSW, reading it from madmp-core's own environment.

## Checking a .env before starting

```bash
bash scripts/setup.sh
```

The script reports the configuration compose will actually resolve, before it
starts anything. Three things it does that reading the file does not:

**It reports the value compose will use, not the value in the file.** The
environment wins over `.env`, so a variable exported in the shell shadows the
file silently. Each line says which of the two it came from.

**It never prints a secret.** The six secret values are reported as `set` or
`MISSING`, and nothing else.

**It names keys `.env.example` has gained since your `.env` was written**, and
reports them rather than copying them in:

```
(!) .env.example carries keys your .env does not: MADMP_CORE_VERSION
    Add them, with a value.
```

That is the check that catches an upgrade needing a new variable.
