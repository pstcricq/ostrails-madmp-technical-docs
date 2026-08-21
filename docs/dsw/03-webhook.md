# Installing the webhook

The submission webhook is not built here. It is an image published by
madmp-core, pulled and run beside DSW, and then declared **inside** DSW as a
Document Submission service.

Two halves, and both are needed: the container has to run, and DSW has to know
about it.

## The container

```yaml
submission:
  image: ghcr.io/pstcricq/ostrails-madmp-core/submission:${MADMP_CORE_VERSION}
  restart: always
  environment:
    SUBMISSION_TOKEN: ${SUBMISSION_TOKEN}
    REGISTRY_TOKEN: ${REGISTRY_TOKEN}
    REGISTRY_OWNER: ${REGISTRY_OWNER}
    REGISTRY_REPO: ${REGISTRY_REPO}
```

**No published port.** DSW reaches it by service name on the compose network,
at `http://submission:8080`, so nothing about it needs to be exposed to the
host. There is a commented `127.0.0.1:8085:8080` in the file for when you want
to poke it from a terminal.

!!! note "Four variables listed one by one, not `env_file: .env`"
    The container holds these four and none of the stack's other secrets. A
    webhook that can read the database password is a webhook whose compromise
    is worse than it needs to be.

The healthcheck calls `/health` with python rather than curl, because the image
carries no curl:

```yaml
test: ["CMD", "python", "-c",
       'import urllib.request; urllib.request.urlopen("http://localhost:8080/health")']
```

## Pulling a private image

!!! warning "A 401 that reads like a missing image"
    The package is private for as long as its repository is, so a host that has
    never run `docker login ghcr.io` fails the pull with a 401 that reads
    exactly like the image does not exist.

```bash
docker login ghcr.io
```

## Choosing the version

```
MADMP_CORE_VERSION=v1.0.0
```

Always a tag, never `latest` and never a branch. That tag decides which engine
and which rules judge a submission, and the verdict committed beside every DMP
records the version that judged it. Two deployments on a moving tag would
report the same version while running different code.

Upgrading is one line and a restart:

```bash
docker compose up -d submission
```

## Declaring it inside DSW

The container running is half the job. DSW will not post anywhere it has not
been told about.

**Do not fill this in by hand.** It is written by madmp-core:

```bash
uv run python -m dsw.publish submission configs/projects/glider.yaml
```

That is what produces the entry below, scoped to the project's own document
template so only its documents can be submitted to it.

![The submission service in DSW](../img/dsw-submission-settings.png)

The mechanics of that write, including why it sends the tenant's whole
configuration back and what protects a change made in the console, are in
[madmp-core → Publishing to DSW](../core/08-publish.md).

## The two values that have to agree

| Value | Set here | Set in DSW by |
|---|---|---|
| the shared secret | `SUBMISSION_TOKEN` in `.env` | `dsw.publish submission`, from madmp-core's own env |
| the webhook's address | nothing, it is a service name | `SUBMISSION_URL` in madmp-core's env |

So `SUBMISSION_TOKEN` exists in **two** environments, this deployment's and the
one `dsw.publish` runs with, and they must carry the same value. A mismatch is
a 401 at submission time and nowhere earlier.

`SUBMISSION_URL` is not a variable of this repository at all. It is the
webhook's address **as DSW reaches it**, and for this deployment that is:

```
http://submission:8080/submissions
```

A compose service name, correct here and wrong on any deployment where the
webhook does not sit on the same network.

## Checking the two halves

The container answers:

```bash
docker compose exec submission python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8080/health').read())"
```

DSW can see it: the Document Submission settings page lists the service and
shows it enabled. Anything else is a publish that has not been run.

## What it needs to be able to do

The registry token is a fine-grained PAT with **Contents read and write** and
**Metadata read** on the registry repository, and nothing else. The webhook
reads three files, compares, and commits three files. It never creates a
repository, never deletes, and never writes outside `projects/<folder>/`.

And the project's folder has to be laid out **before** a submission arrives.
The webhook checks for `projects/<folder>/template/.gitkeep` and refuses if it
is not there, rather than creating a half-folder. Laying it out is madmp-core's
`registry-sync` job. See
[madmp-core → registry/ and scripts/](../core/11-registry.md).
