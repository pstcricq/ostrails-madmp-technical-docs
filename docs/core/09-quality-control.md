# quality_control/ : the verdict

`run_qc()` walks the merged model and one document together, once, and returns
a flat list of `CheckResult`: plain data, with nothing of a runner or a report
in it.

```bash
uv run python -m quality_control.run \
    --pins configs/projects/glider.yaml \
    --dmp  build/dmp.json \
    --json qc_results.json
```

Exit code 0 when the document has no real violation, 1 otherwise.

## Four statuses, one rule

| Status | Means |
|---|---|
| `fail` | a real violation |
| `warning` | a present value outside a **recommended** vocabulary, the only source of warnings |
| `missing` | an optional field is absent, which follows from cardinality alone and is never an error |
| `pass` | present and valid |

A `fail` is one of: a required field missing, a JSON shape the cardinality does
not allow, a wrong type or format, a value outside a strict `allowed_values`
vocabulary, or a key no rule declares.

There is exactly one PASS/FAIL rule, and it is one line:

```python
def has_failures(results: Iterable[CheckResult]) -> bool:
    return any(r.status == "fail" for r in results)
```

**Warnings never fail a document.** A recommended vocabulary is a
recommendation, and the whole point of the distinction made in
[2. rules/](02-rules.md) is that it stays one here.

## An empty string is an absence

The single most important behaviour in this module.

```
"ethical_issues_exist": ""
```

The document template emits every required scalar unconditionally, so `""` is
what an unanswered question renders as. Reading it as a value would let a
required field nobody answered pass both its presence check and its type check,
which is exactly the failure the quality control exists to catch.

!!! warning "A string of spaces is a value"
    `" "` is content someone typed, and it stays a value. Only the truly empty
    string is read as an absence. The line is drawn there on purpose: trimming
    would mean deciding that whitespace is never meaningful, which is not this
    module's call to make.

## The seven categories

| Category | Asks |
|---|---|
| `structure` | does the document hold a top-level `dmp` object |
| `presence` | is a declared field there |
| `shape` | does the JSON match the cardinality: single value or array, object where an object is declared |
| `type` | does a scalar match its declared format |
| `allowed_values` | is a value inside a closed vocabulary |
| `suggested_values` | is a value inside a recommended one |
| `unexpected` | is there a key **no rule declares** |

`unexpected` asks the question the other way round. Every other category walks
the model and looks into the document. That one walks the document and looks
into the model, which is what catches a field that was renamed in the rules but
not in a hand-edited plan.

## Formats are regexes, and deliberately shallow

```python
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LANGUAGE_RE = re.compile(r"^[a-z]{3}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_URL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://\S+$")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")
```

`language` is three lowercase letters, which is ISO 639-3's shape and not its
list. `currency` is three uppercase letters, not a check against ISO 4217. The
choice is to validate the shape and not the membership: a vocabulary that
changes outside this repository would otherwise start failing documents that
were correct when written.

## Two paths per result

```python
@dataclass(frozen=True)
class CheckResult:
    category: str
    status: str
    rule_path: str      # "dmp.dataset[].distribution[].title"
    instance_path: str  # "dmp.dataset[0].distribution[2].title"
    standard: str
    message: str
```

`rule_path` names the rule, `instance_path` names the concrete spot in the
document. With one you find the declaration, with the other you find the value.
A plan with forty datasets produces forty results sharing one `rule_path`.

`standard` is the standard that introduced the field, and where a constraint
was imposed by an extension rather than by the base, the message says so, read
from the tightenings the merge recorded.

## The envelope

`envelope()` produces the one shape a verdict is written and read in. The
command writes it, and the webhook commits it.

```json
{
  "dmp": "projects/glider/template/dmp_glider_template.json",
  "standards": ["rda_dcs", "ostrails"],
  "rules_versions": { "rda_dcs": "1.0.0", "ostrails": "1.0.0" },
  "verdict": "pass",
  "engine": "1.0.0",
  "summary": { "total": 106, "fail": 0, "warning": 0, "missing": 30, "pass": 76 },
  "fail": [],
  "warning": [],
  "missing": [ ... ],
  "pass": [ ... ]
}
```

**Four lists, one per status**, rather than one flat list plus a filter. A
reader shows them by severity without doing any work, and
`len(envelope[status])` equals `envelope["summary"][status]` for each of the
four, so the summary cannot drift from the lists it summarises.

`engine` is `version("madmp-core")`, read from the installed package metadata.
It says which release judged the plan, which is why the tag and
`pyproject.toml` are checked against each other before anything is published.

!!! warning "No timestamp, on purpose"
    A timestamp would change the bytes at every check of an unchanged
    document, and the webhook commits this file. A caller could then never
    report a plan as unchanged, and every re-submission would produce a commit
    saying nothing happened.

## Reading the pins

`--pins` names the file carrying the rules versions to check against, in the
`rules: [{standard: version}, ...]` shape. **Two files are written in that
shape and both are read here**: a project config (YAML), and the provenance
file a submission commits beside its DMP (JSON). The suffix decides which
parser is used.

That is what lets a plan be re-judged years later against the rules it was
written against, rather than against today's.
