# Operating it

## Starting

```bash
bash scripts/setup.sh
```

The one script, and it wraps two commands:

```
docker compose up -d --wait
docker compose run --rm createbucket
```

It writes nothing and can be re-run. Before it starts anything it reports the
configuration compose will resolve, refuses on a missing value, and names any
key `.env.example` has gained since your `.env` was written. What each of those
checks catches is in [2. Configuration](02-configuration.md).

`--wait` is what makes it honest: it returns once every healthcheck passes, not
once the containers exist.

At the end it says where the instance is, and warns if the seeded demo accounts
still answer:

```
 (!) The seeded demo accounts still open this instance:
         albert.einstein@example.com / password
     Create your own admin and delete these three before this instance
     is reachable from anywhere but this machine.
```

!!! danger "That warning is not decorative"
    It only prints when the account **really answers**, because the script
    tries to log in. Three seeded accounts with published passwords open a DSW
    instance completely.

## Everyday commands

```bash
docker compose ps
```

```bash
docker compose logs -f server
```

```bash
docker compose exec postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Restart one service after changing its variable:

```bash
docker compose up -d submission
```

## Stopping, and the difference that matters

```bash
docker compose down
```

Stops and removes the containers. **The data stays.**

```bash
docker compose down -v
```

Removes the two volumes as well, so the database and the object storage go
with them. That is how a clean run starts, and it is the only way to change
`POSTGRES_PASSWORD`, `POSTGRES_USER` or `POSTGRES_DB` on an existing
deployment, since those are applied at the very first `initdb` only.

## Upgrading DSW

One variable, three images:

```
DSW_VERSION=4.31
```

```bash
docker compose up -d
```

The server applies its migrations on start, which is what the 300 second
`start_period` on its healthcheck leaves room for.

!!! warning "Two version numbers in madmp-core move with it"
    A DSW upgrade is not only this variable. `METAMODEL_VERSION = 20` and
    `TEMPLATE_METAMODEL_VERSION = "18.0"` in madmp-core are tied to the
    instance, and the bundles it generates have to match what the new version
    accepts. Check those, and the matching schema in
    [dsw-schemas](https://github.com/ds-wizard/dsw-schemas), before upgrading a
    stack that already holds projects.

## When something is wrong

**The stack does not come up.** `scripts/setup.sh` says so and points at the
logs. `docker compose config --quiet` on its own catches the one class of
error a key-by-key check cannot: a multi-line value left without its quotes,
which makes compose read every following line as a new variable.

**The client loads but nothing works.** `API_URL` is resolved by the browser,
not by a container. A compose service name there produces exactly this.

**A document renders but will not download.** `S3_URL` goes inside the
presigned URL the browser follows. If it resolves from the containers but not
from the browser, everything works until the download.

**A submission returns 401.** `SUBMISSION_TOKEN` differs between this
deployment and the environment `dsw.publish submission` ran with.

**A submission returns "not initialized".** The project's folder was never laid
out in the registry, or the token cannot see it. The message names both, because
they look the same from here.

**The webhook will not pull.** `docker login ghcr.io`, see
[3. Installing the webhook](03-webhook.md).

## Deploying somewhere else

Two decisions this repository does not make, and both **remove** services
rather than adding any.

**Keep MinIO, or point at an existing S3.** Dropping the `minio` and
`createbucket` services means `S3_URL`, `S3_USERNAME`, `S3_PASSWORD` and
`S3_BUCKET` name someone else's storage.

**Keep the Postgres container, or use a managed instance.** The connection
string is currently assembled in the compose file with `@postgres:5432` hard
coded. Moving to a managed database means putting the whole
`DATABASE_CONNECTION_STRING` in `.env`, which is the name DSW natively expects
anyway.

And in both cases, the `127.0.0.1:` prefixes come off only if a proxy sits in
front. The correction for a proxy belongs in the proxy
(`proxy_redirect http:// https://`), not in a file that masks the client
image's own.
