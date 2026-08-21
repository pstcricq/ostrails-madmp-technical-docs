# The three files

Written together, in one commit, by the submission webhook. Read below in the
order a reader needs them: the plan, what it was built from, and how it fared.

## dmp_&lt;id&gt;_template.json

The DMP itself. RDA DCS shape, with the OSTrails extension fields where they
were answered.

```json
{
  "dmp": {
    "created": "2026-08-21T07:21:13.401022Z",
    "ethical_issues_exist": "no",
    "language": "eng",
    "modified": "2026-08-21T07:29:58.720239Z",
    "title": "Glider observations along the Canales line",
    "contact": {
      "mbox": "data.centre@socib.es",
      "name": "SOCIB Data Centre",
      "contact_id": [{ "identifier": "0000-0002-1825-0097", "type": "orcid" }]
    },
    "dmp_id": {
      "identifier": "https://raw.githubusercontent.com/pstcricq/ostrails-madmp-registry/main/projects/glider/template/dmp_glider_template.json",
      "type": "url"
    },
    "description": "End-to-end test plan for the SOCIB glider pilot.",
    "version": "1.0.0",
    "dataset": [
      {
        "dataset_id": { "identifier": "10.25704/glider-canales-e2e", "type": "doi" },
        "personal_data": "no",
        "sensitive_data": "no",
        "title": "CTD profiles, Canales line",
        "description": "Temperature and salinity profiles from a glider mission."
      }
    ]
  }
}
```

### dmp_id is this file's own raw URL

```
https://raw.githubusercontent.com/<owner>/<repo>/main/projects/<id>/template/dmp_<id>_template.json
```

A plan's identifier should be where the plan lives, and this is where it lives.
The document template set it to the DSW project URL as a placeholder, and the
webhook rewrote it at the moment of the commit, which is the first moment a
permanent address existed.

!!! danger "The branch is part of every identifier ever issued"
    That URL names `main`. Moving this repository to another default branch
    would leave every `dmp_id` ever written pointing nowhere.

### created and modified are DSW's dates

Not the researcher's answers. They come from the DSW project's own `createdAt`
and `updatedAt`, because the config sets `auto_timestamps: true`. See
[madmp-core → Generating the document template](../core/07-document-template.md).

### There is no metadata key here

The rendered document carried two top-level keys, `dmp` and `metadata`. The
webhook takes the second one out and writes it to its own file, so this file is
a maDMP and nothing else. Anything reading it as an RDA DCS document finds
exactly what it expects.

## dmp_&lt;id&gt;_template.meta.json

The provenance: what this DMP was built from.

```json
{
  "project": "glider",
  "template_version": "1.0.0",
  "rules": [{ "rda_dcs": "1.0.0" }, { "ostrails": "1.0.0" }]
}
```

| Key | Is |
|---|---|
| `project` | the project id, which is also this folder's name |
| `template_version` | the version of the project config the document was rendered from |
| `rules` | the pinned standards, in the config's own `rules:` shape |

**`rules` is written in the same shape a project config uses.** That is what
lets `quality_control.run` read either file for its `--pins`:

```bash
uv run python -m quality_control.run \
    --pins  projects/glider/template/dmp_glider_template.meta.json \
    --dmp   projects/glider/template/dmp_glider_template.json
```

So a plan can be re-judged years later against **the rules it was written
against**, rather than against today's. That is the whole reason this file
exists as a separate artifact rather than as a header inside the DMP.

## dmp_&lt;id&gt;_template.check.json

The verdict, in the envelope shape
[quality_control](../core/09-quality-control.md) produces.

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

### Four lists, and a summary that cannot drift

`len(envelope[status])` equals `summary[status]` for each of the four, by
construction. A reader shows results by severity without filtering anything.

Each entry is one check on one concrete spot:

```json
{
  "category": "presence",
  "status": "missing",
  "rule_path": "dmp.dataset[].distribution[]",
  "instance_path": "dmp.dataset[0].distribution",
  "standard": "rda_dcs",
  "message": "Optional field 'dmp.dataset[0].distribution' is absent."
}
```

`rule_path` finds the declaration, `instance_path` finds the value.

### verdict is only ever pass here

A document that fails never reaches this repository. The webhook refuses it and
tells the researcher why while they are still in DSW. So `"verdict": "fail"` in
a committed file would mean something went wrong in a way the pipeline does not
allow, not that a plan was accepted with violations.

`"warning"` may well be non-empty. Warnings do not block.

### engine says which release judged it

```json
"engine": "1.0.0"
```

Read from the installed package metadata of madmp-core, which is why the CI
refuses a tag that disagrees with `pyproject.toml`. Without that check, a
verdict could name a release nobody can check out.

!!! note "No timestamp, and that is what makes re-submission quiet"
    Checking an unchanged document produces byte-identical bytes, so a
    re-submission that changes nothing commits nothing. A timestamp here would
    make every re-submission a commit saying nothing happened.
