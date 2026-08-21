# project/ : the merged model

Several standards describe the same DMP. `merge_rules()` turns them into one
tree of immutable `Field` nodes, and refuses any combination that would make
the result depend on how the pins were written.

This is the page to read before any other. Everything downstream consumes the
`Model` and nothing else.

## The merged types

```python
@dataclass(frozen=True)
class Field:
    name: str
    path: tuple[str, ...]        # ("dataset", "title")
    dotted_path: str             # "dmp.dataset[].title"
    cardinality: str
    type: str
    origin: str                  # the standard that introduced this field
    description: str | None = None
    chapter_description: str | None = None
    allowed_values: tuple[str, ...] | None = None
    suggested_values: tuple[str, ...] | None = None
    tightenings: tuple[Tightening, ...] = ()
    children: tuple[Field, ...] = ()
```

Two derived properties carry the cardinality rule so no consumer has to
re-read the table: `is_list` is true for `1..n` and `0..n`, `is_required` for
`1` and `1..n`. `walk()` yields the field then every descendant, depth-first,
and `Model.walk()` does the same over the whole tree. That pair is the entire
traversal API, and it is what the generators and the quality control all use.

`dotted_path` marks list-ness with `[]`, which is why messages read
`dmp.dataset[].title` and not `dmp.dataset.title`.

## Every extension is judged against the base

This is the load-bearing sentence of the module.

> Every extension is judged against the base, never against what another
> extension already imposed.

`_Node` keeps two dictionaries for that reason: `base_meta`, what the base
standard declared, and `meta`, the merged state so far. Every check reads
`base_meta`.

```python
base_card, addition_card = base_meta["_cardinality"], raw["_cardinality"]
if addition_card != base_card:
    # Against the base's cardinality, not the merged one, so an extension
    # that redeclares what the base says stays a no-op even once another
    # has tightened it.
```

The consequence: what the extensions require then **combines** rather than
chaining. Cardinalities combine as "required wins", vocabularies as an
intersection. Both are commutative, so the merged model does not depend on
the order the pins are written in.

## What an extension may do

| Move | Verdict |
|---|---|
| redeclare a field identically | allowed, and a no-op |
| `0..1` → `1`, `0..n` → `1..n` | tightening, recorded |
| a vocabulary restricted to a subset of itself | tightening, recorded |
| an open field given a vocabulary | tightening, recorded |
| `_suggested_values` closed into `_allowed_values`, over its own values | tightening, recorded |
| describe a field the base left undescribed | allowed |
| repeat the base's description word for word | allowed |
| `1` → `0..1`, `1..n` → `0..n` | **conflict**, loosening |
| single ↔ list (`1` → `1..n`) | **conflict**, reshaping |
| a different `_type` | **conflict** |
| a wider vocabulary | **conflict** |
| `_allowed_values` offered back as `_suggested_values` | **conflict** |
| a different description | **conflict** |

Redeclaring identically is not a curiosity, it is the common case: it is what
repeating a structural parent to reach a new leaf field looks like. The
`dataset` block in `ostrails/1.0.0.json` exists only to carry four new
children, and says nothing else.

## Why closing what is suggested is only sometimes a tightening

The subtle one. A base that **suggests** `["handle", "doi", "ark", "url"]` is
saying all four are reasonable. An extension that **closes** the field on
`["doi"]` is a tightening: it forbids three values the base merely recommended.
An extension that closes it on `["doi", "swh"]` is not, because `swh` was
never on the table.

```python
return (
    f"{dotted}: {origin} closes the vocabulary on {outside}, which "
    f"{node.origin} does not recommend, closing what is suggested is a "
    f"tightening only over the values the base suggests, here it would "
    f"forbid {sorted(set(ref) - set(addition))}, which it recommends."
)
```

The reverse move is refused outright, and the message says why in terms of
what it would do to a verdict:

```python
return (
    f"{dotted}: {origin} offers _suggested_values where {node.origin} "
    f"closed the vocabulary with _allowed_values, that turns a "
    f"violation into a warning, and an extension may only tighten."
)
```

!!! note "A field holds at most one vocabulary"
    The closed/recommended pair is read as a **single fact with a nature**,
    not as two independent keys. Changing that nature is a move like any
    other: closing a recommended vocabulary tightens, and the reverse is
    refused. When a closing extension wins, the recommendation is deleted
    rather than kept, because it has become false.

## Vocabularies keep the base's order

When two standards restrict the same vocabulary, the merged values are the
intersection, ordered as the base ordered them:

```python
order = node.base_meta.get(_vocabulary_key(node.base_meta) or "", state)
combined = _ordered_like(order, sorted(set(state) & set(addition)))
```

A restriction therefore never reorders what the researcher reads in the
questionnaire. An intersection that comes out empty is a conflict: no value
would satisfy both standards.

## Tightenings are recorded, not just applied

Every accepted restriction leaves a `Tightening` on the field.

```python
@dataclass(frozen=True)
class Tightening:
    standard: str
    aspect: Literal["cardinality", "allowed_values", "suggested_values"]
    before: Any
    after: Any
```

`before` is **the base's declaration**, not the state this standard happened
to find, so a tightening says what its standard requires beyond the base
whatever order the others merged in.

That record is what lets a message downstream name the standard responsible.
The quality control uses it to say when a constraint came from an extension
rather than from the base, and the questionnaire uses it for the standard tags
on each question.

![Standard tags on generated questions](../img/questionnaire.png)

## Two phases, each complete

```python
return _build_model([(str(p), load_rules_file(p)) for p in rules_paths])
```

Every file goes through the rules loader first, so nothing is merged that is
not already schema-valid. Then:

**Phase 1, is the set well-formed.** Exactly one base standard, found by its
own `"extends": false` declaration so input order does not matter, and no
standard name declared twice. Raises `RulesSetError`.

**Phase 2, do they merge.** Every conflict across every file is collected and
raised together in one `RulesConflictError`.

Neither phase stops at the first problem. A rules change that breaks four
fields tells you about four fields.

## The errors a caller may see

`assemble_project()` lets each step raise its own kind, unchanged:

| Error | Means |
|---|---|
| `ConfigFileError` | the project config is malformed |
| `UnresolvedPinsError` | a pin names a file that is not there |
| `RulesFileError` | a rules file is malformed |
| `RulesSetError` | the set of files is ill-formed |
| `RulesConflictError` | two standards disagree |

All five carry every problem of their phase, so one run tells you everything
that is wrong at that stage.
