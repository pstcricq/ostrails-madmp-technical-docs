# The UUID convention

Every DS Wizard entity generated from the rules takes its identity from the
**path of the field it was generated for**. Not from a counter, not from a
lookup table, not from `uuid4()`.

`dsw/uuids.py` is the whole of it, and it knows nothing but the standard
library and the shape of a field path.

```python
NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000000")


def u(*parts: str) -> str:
    """Derive a deterministic entity UUID from a sequence of name parts."""
    return str(uuid.uuid5(NAMESPACE, "::".join(parts)))
```

## The derivations

| Entity | Derivation |
|---|---|
| chapter | `u("chapter", key)` |
| question | `u(*path, "question")` |
| one answer of an options question | `u(*path, "answer", value)` |
| the synthetic **Other** answer | `u(*path, "answer", "other")` |
| its free-text follow-up question | `u(*path, "other-followup", "question")` |
| the item question of a repeated scalar | `u(*path, "item-value", "question")` |
| the Yes/No gate of a `0..1` object | `u(*path, "has-question")` |
| its Yes answer | `u(*path, "has-answer", "yes")` |
| its No answer | `u(*path, "has-answer", "no")` |

The synthetic **Other** is by construction `answer_uuid()` of the value
`"other"`, which is exactly why a vocabulary that already lists that word does
not get a second one: the declared answer and the synthetic one would be the
same entity. That rule lives in `needs_a_synthetic_escape()`, described in
[2. rules/](02-rules.md).

## What it buys

**Two generators agree without talking to each other.** The Knowledge Model
generator and the document template generator both need the UUID of the
question for `dmp.contact.mbox`. Neither passes it to the other and neither
reads a table. They both call `question_uuid(("contact", "mbox"))` and get the
same answer.

**Publishing is idempotent.** Regenerating a package produces byte-identical
identities, so republishing the same version is a no-op rather than a new set
of entities.

**A project survives a rules change.** A researcher's answers are stored
against question UUIDs. Because a question keeps its identity as long as its
field keeps its path, adding a field elsewhere in the tree does not orphan a
single existing answer.

## Verifying it

The derivation can be checked against a built bundle without trusting either
side, which is worth doing after any change near this module:

```python
from dsw.uuids import question_uuid

question_uuid(("contact", "mbox"))
# '41074dea-dc4b-5b8b-909a-b022987cf246'
```

| Field path | Question UUID |
|---|---|
| `title` | `a378983e-92e8-5e65-81c0-a0b50727b377` |
| `language` | `7b0592f8-156f-5de5-b099-173d39e74928` |
| `contact.mbox` | `41074dea-dc4b-5b8b-909a-b022987cf246` |
| `contact.contact_id` | `34c28ed2-b193-5502-bb9c-2aa158ff5a5a` |
| `dataset.dataset_id.identifier` | `dc3b0a11-3e69-5fbc-9167-b417e4bbf629` |
| `dataset.personal_data` | `8eb6c4d3-89de-52c8-b0ad-0d3d841f594e` |

Those are the UUIDs in the published `socib:glider:1.0.0` bundle, and they are
what a reply path in DS Wizard is built from. See
[Annexes → An end-to-end run](../annexes/01-end-to-end.md) for how a reply
path composes.

!!! danger "Frozen"
    The namespace above and every literal part string passed to `u()` are the
    identity of every entity in every published Knowledge Model and document
    template. Change one, and every derived UUID changes: published packages
    stop matching, and every stored answer in every existing project is
    orphaned.

    The tests hold the derived values, so a change here fails immediately
    rather than at publication time. Do not "fix" those expectations.

## Why a nil namespace

`uuid5` needs a namespace, and the usual choices (`NAMESPACE_URL`,
`NAMESPACE_DNS`) would claim these identifiers are URLs or domain names, which
they are not. The nil UUID claims nothing. What makes a collision impossible
here is the part strings, which are unique per entity kind by construction, not
the namespace.
