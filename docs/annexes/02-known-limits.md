# Known limits

What is known not to work, not to be finished, or to be true only under
conditions worth stating. Nothing here is a bug report: each of these is a
choice, an unbuilt half, or a constraint someone will meet.

Where a limit is held open on purpose, it says **what would make it worth
re-judging**, because the answer is usually a change in circumstances rather
than a change of mind.

## Not built yet

**`productions/` is empty, and nothing writes to it.** Every project folder
carries the subdirectory, and `SUBDIRS` names it, but the only writer of a DMP
is the webhook and it writes to `template/` alone. The deployment DMPs, derived
from the template with its `{snake_case}` placeholders resolved, have a place
and no producer.

**One output format.** `FORMATS` lists two, and only the first is `available`:

```python
{"name": "JSON-LD", "available": False,
 "notes": "Linked-data version of the same output. Not implemented yet."}
```

The unavailable entry is deliberately kept in the list rather than deleted, so
it appears in the generated README as not implemented instead of not existing.

**No migration path for a published Knowledge Model.** Publishing is idempotent
through the version, and bumping the version publishes a new package. Nothing
here migrates a project sitting on the old one: DSW has its own migration
feature, and using it is a manual step nobody has automated.

## Not verified

### Nothing confronts the generated artifacts with a real DSW instance

`METAMODEL_VERSION = 20` and `TEMPLATE_METAMODEL_VERSION = "18.0"` describe the
instance, not the project, and **nothing in the repository checks that a given
instance accepts them**, nor that the emitted Jinja actually renders.

What is checked, and it is less than it sounds:

- the template body **parses**, for every project, in `validate_generation.py`
- the tests **render** it with DSW's three filters (`reply_path`,
  `reply_str_value`, `reply_items`) replaced by doubles

So a disagreement about what one of those filters does would only show at run
time, in DSW, in front of a researcher.

The KM bundle is on firmer ground: it was checked against the official
`kmp_schema_v20.json` with zero errors, and a test enumerates the metamodel's
fields. But that confronts the **schema**, not an instance.

!!! note "Why it stops there"
    An instance is reachable from CI, and the `publish` job has exercised it
    end to end. But it is still under development: it does not answer every
    time, and it does not keep published packages. A test depending on it would
    go red for reasons foreign to this repository, which is the worst kind of
    test.

    **Worth re-judging when** that instance is stable. The question then becomes
    "publish, then render a test DMP" rather than "imitate the filters better".

### The formatting of the data files is not checked

`ruff format` touches neither JSON nor YAML, so nothing in CI checks the layout
of `rules/standards/*.json` or `configs/projects/*.yaml`. Their **content** is
validated, by `validate_rules.py` and `validate_configs.py`. Their formatting is
not.

!!! note "Why not prettier"
    It would need Node in a purely Python CI: a `package.json`, an npm
    lockfile, a cache, a second dependency system. The `npx --yes` version
    avoids that but pulls an unpinned release on every run, which reintroduces
    exactly the problem `uv sync --frozen` solves. The cost is real, the stake
    is cosmetic.

    **Worth re-judging when** somebody other than the current author edits the
    rules files, or when a rules diff becomes hard to read through the noise. A
    versioned `.prettierrc` answers the first case for three lines and zero
    seconds of CI.

## Where it breaks

### An unvalidated pin raises TypeError, not UnresolvedPinsError

`resolve_pins` takes the shape of a pin for granted, because
`config.schema.json` already requires a list of single-key mappings of strings.

```python
resolve_pins([{"ostrails": 1.0}], ...)
# TypeError: argument should be a str or an os.PathLike object
```

A bare `TypeError`, not the `UnresolvedPinsError` a caller would catch.

**Latent, not active**: the only caller is `assemble_project()`, which loads the
config first.

!!! warning "Worth re-judging when"
    The first caller passes pins that do **not** come from a validated config.
    The candidate is the quality control, which reads the pins a submitted DMP
    carries with it, from a file with no schema at all that nobody validates on
    the way in. The fix is decided with that caller in view: either a shape pass
    in `resolve_pins`, or a schema for that file.

### A file over 1 MB cannot be read

GitHub's Contents API inlines a file's content up to 1 MB and answers with an
empty `content` beyond it. That read is what compares a submission with what the
registry already holds.

**The read now raises** rather than returning that emptiness, so a DMP of that
size fails the submission. Before, the webhook never found it equal to what it
held, and recommitted it on every send while reporting `updated`, with nothing
saying so.

A silent degradation became a failure, which is not the same thing as a
guarantee.

Only the read is affected. A commit carries its files as tree entries and has no
such limit.

### The webhook has neither retry nor quota handling

GitHub answering 403 or 429 comes back to DSW as a 502. Acceptable for an
instance that submits occasionally, and not for one that does not.

### The quality control never judges two values together

Every value is checked alone, against the rule that declares it. Nothing
compares two values with each other, so:

- two datasets with the same title pass
- two distributions pointing at the same `access_url` pass
- a `modified` earlier than `created` says nothing

There are no conditional rules either, of the kind "if `ethical_issues_exist`
is `yes` then `ethical_issues_description` becomes required".

!!! note "It is a limit of the rules format before it is a limit of the engine"
    A rules file describes a tree of fields, each carrying its cardinality, its
    type and its vocabularies, and it has **no way of speaking about a field
    other than itself**. Lifting this would mean inventing that expression in
    `rules.schema.json` first, and then a second walk of the document, since a
    cross-check cannot be decided during the descent that discovers it.

    Accepted as it stands: what the quality control guarantees today, field by
    field, is what it is asked for.

## Held by discipline, not by a check

### Nothing prevents republishing a tag that is already published

GHCR accepts a push onto an existing tag and overwrites it without a word. The
rule "a published tag is never rewritten" is therefore held by hand.

Two deployments pinning `v1.0.0` would then run different code while announcing
the same version, and the verdict committed beside every DMP would carry that
number on both sides.

What limits the damage: `version` refuses a tag that disagrees with
`pyproject.toml`, so republishing `v1.0.0` requires the package version to still
be `1.0.0`, meaning nothing was released in between. **The case that still gets
through is retagging the same number onto another commit.**

Closing it would take a step that asks GHCR before pushing and refuses a tag
already there. Not built: the discipline is enough for a repository with one
author, and the day that is no longer true, that step is what to add.

## Deliberately shallow

**Formats are validated by shape, not by membership.** `language` is three
lowercase letters, which is ISO 639-3's shape and not its list. `currency` is
three uppercase letters, not a check against ISO 4217. Validating membership
would mean a vocabulary maintained outside this repository could start failing
documents that were correct when they were written.

**Several rules types collapse onto `String` in the questionnaire.**
`country_code`, `currency` and `language` have no DSW value type, so a typo in
one is caught by the quality control at submission, not by the questionnaire at
typing. The check is not lost, only late.

**An empty string is an absence, a string of spaces is a value.** Trimming
before that decision would mean ruling that whitespace is never meaningful,
which the quality control declines to decide for every field of every standard.

## True only under conditions

**The submission service URL is right for exactly one deployment.**

```
http://submission:8080/submissions?project=glider
```

That is the webhook's address as DSW reaches it on the compose network of
`madmp-dsw`. Published against any other topology it is wrong, and nothing in
the code can tell the two apart. It fails at submission time, never at publish
time.

**Everything is bound to `127.0.0.1`.** So a GitHub runner cannot reach a local
stack, which is why `publish` in CI is conditional on `vars.DSW_API_URL` and a
local instance is published to by hand. Widening the binding is not the fix, a
proxy is.

**`S3_URL` has to resolve identically from a container and from a browser.** It
is both the address of the object storage and what goes inside the presigned
download URLs. `host.docker.internal` handles that on Docker Desktop and
nowhere else.

**A DSW upgrade is not one variable.** `DSW_VERSION` moves three images, but the
two metamodel versions in madmp-core are tied to the instance too, and the
matching schema in [dsw-schemas](https://github.com/ds-wizard/dsw-schemas) is
`additionalProperties: false`, so a bundle built for the wrong metamodel is
rejected rather than degraded.

## Rough edges

**`RULES_DIR` is defined in `project/assemble.py`** and imported from there by
`quality_control/run.py` and `submission/service.py`, neither of which assembles
anything. It is the resource root, not an assembly concern, so its placement is
wrong even though its value is right. Flagged, not moved.

**`api_url` on the GitHub client is configurable and unused.** It would allow
GitHub Enterprise. Nothing passes it, the tests included.

**madmp-core has no LICENSE file.** `madmp-dsw` carries one, `madmp-registry`
and this documentation repository do not either. The project configs declare
`license: "CC BY 4.0"` for the generated packages, which is a different thing
from the licence of the code that generates them.

**Mail is disabled**, and the `mailer` service is commented out rather than
deleted, because enabling one without the other fails silently: the server
queues commands nobody processes and the interface still reports the message as
sent.

**The seeded demo accounts open a fresh instance completely.** DSW seeds three
whose credentials are published. `scripts/setup.sh` warns while they still
answer, and that is all it does.

## Screenshots in this site

Every image under `docs/img/` is regenerated by `scripts/screenshots.py` against
a **running** DSW that has been through the run in
[1. An end-to-end run](01-end-to-end.md). There is no fallback: without an
instance holding a project named `Glider mission test`, the script exits rather
than producing something misleading.

It also masks every field holding a secret before capturing, and re-reads the
page to refuse a capture if one survived. That guard exists because the Document
Submission settings page renders the webhook's shared secret in clear, about a
thousand pixels down a page this site photographs and publishes.
