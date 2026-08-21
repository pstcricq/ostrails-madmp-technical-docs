"""Regenerate every DS Wizard screenshot under ``docs/img/``.

    uv run --group dev python scripts/screenshots.py

Screenshots go stale. The one in the older documentation site still shows a CI
run with seven jobs against a pipeline that has eleven, and nobody noticed
because remaking it meant remembering which pages to open and at what size.
This script makes the images a build product: point it at a running DSW that
has been through the end-to-end run, and every picture in the site is remade
at the same viewport, from the same state, in one command.

It signs in the way the rest of this project does, by asking the API for a
token with the credentials in the environment, then writing that token into
the client's ``localStorage`` under ``session/wizard``, which is where the
client looks. No password is ever typed into the login form.

Four variables, no defaults for the two secrets:

    DSW_API_URL     e.g. http://localhost:3000/wizard-api
    DSW_CLIENT_URL  e.g. http://localhost:8080/wizard
    DSW_EMAIL       an account that can see the project and the settings
    DSW_PASSWORD

(!!) The project is found by name rather than by uuid. A uuid changes every
time the stack is reset, and a script that needs editing after every reset is
a script that stops being run.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
IMG_DIR = ROOT / "docs" / "img"

# The name given to the project the end-to-end run creates. Its questionnaire,
# its settings and its documents are most of what there is to show.
PROJECT_NAME = "Glider mission test"

# One size for every image, so no two screenshots in the site are at different
# scales. Doubled on capture, which is what makes text readable when a reader
# opens the picture full size.
VIEWPORT = {"width": 1280, "height": 800}
SCALE = 2


@dataclass(frozen=True)
class Shot:
    """One picture: where to go, what to wait for, what to frame."""

    name: str
    path: str
    # A selector to wait for before capturing. Without it the page is caught
    # mid-render, and a screenshot of a spinner is worse than no screenshot.
    ready: str
    # A selector to frame on. None captures the viewport, which is what a
    # reader of a list or a settings page expects to see.
    crop: str | None = None
    # A chapter to open first. The questionnaire is one route whatever chapter
    # is on screen, so reaching a given chapter means clicking it.
    click: str | None = None
    # A selector to scroll into view first, for a question that sits far down a
    # long questionnaire.
    scroll_to: str | None = None
    description: str = ""


def shots(project_uuid: str) -> list[Shot]:
    """Every screenshot the site uses, in the order the site uses them."""
    project = f"/projects/{project_uuid}"
    return [
        Shot(
            name="km-list",
            path="/knowledge-models",
            ready="text=SOCIB Glider",
            description="The generated Knowledge Model, published and released.",
        ),
        Shot(
            name="template-list",
            path="/document-templates",
            ready="text=SOCIB Glider",
            description="The generated document template, beside its KM.",
        ),
        Shot(
            name="questionnaire",
            path=project,
            ready="text=DMP General Information",
            description="The questionnaire the rules generated, chapter by chapter.",
        ),
        Shot(
            name="questionnaire-list-question",
            path=project,
            ready="text=DMP General Information",
            click="text=3. Contact",
            description="A 1..n field became a list question, with one item.",
        ),
        Shot(
            name="questionnaire-vocabulary",
            path=project,
            ready="text=DMP General Information",
            click="text=3. Contact",
            # (!!) Scrolls to an answer label rather than to the question
            # title. Every question title also appears in the chapter menu on
            # the left, which matches first and is already on screen, so
            # scrolling to it moves nothing.
            scroll_to="text=openid",
            description=(
                "A vocabulary became answers, plus the synthetic Other escape."
            ),
        ),
        Shot(
            name="project-settings",
            path=f"{project}/settings",
            ready="text=SOCIB Glider",
            description="The KM and the document template a project resolves to.",
        ),
        Shot(
            name="project-documents",
            path=f"{project}/documents",
            ready="text=Submitted",
            description="The rendered maDMP, and the submission that committed it.",
        ),
        Shot(
            name="dsw-submission-settings",
            path="/settings/submission",
            # (!!) Not the service name. It appears on this page only inside a
            # closed <select>, which is in the DOM and never visible, so
            # waiting on it waits forever.
            ready="text=Supported Formats",
            description="The submission service, as published by dsw.publish.",
        ),
    ]


def api(url: str, path: str, body: dict | None = None, token: str | None = None):
    """One call to the DSW API, JSON in and JSON out."""
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        url.rstrip("/") + path, data=data, headers=headers
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read() or "{}")


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"error: {name} is not set. See the docstring of this script.")
    return value


def secrets() -> list[str]:
    """Every value in the environment that must never reach an image.

    Read from the environment rather than named in the code, so that adding a
    secret to a deployment adds it here too.
    """
    names = ("SUBMISSION_TOKEN", "REGISTRY_TOKEN", "DSW_PASSWORD")
    return [value for name in names if (value := os.environ.get(name))]


def find_project(api_url: str, token: str, name: str) -> str:
    """The uuid of the project called ``name``, or a readable failure."""
    listing = api(api_url, "/projects?size=100", token=token)
    projects = listing.get("_embedded", {}).get("projects", [])
    for project in projects:
        if project.get("name") == name:
            return project["uuid"]
    found = ", ".join(repr(p.get("name")) for p in projects) or "none"
    sys.exit(f"error: no project named {name!r} on this instance. Found: {found}.")


# Blanks any field holding a secret, just before the shutter.
#
# (!!) This is not belt and braces, it is load-bearing. The Document
# Submission settings page renders the webhook's shared secret in an
# Authorization field, in clear, 1000px down a page this script photographs
# and commits to a public repository. Framing alone kept it out of the picture,
# and framing changes with a viewport, a theme or a DSW release. Masking the
# value does not.
#
# A placeholder rather than an empty box: a reader has to see that a secret
# belongs there, which is half of what the picture is for.
# (!!) One argument, an object. page.evaluate passes a single value, so a
# two-parameter function receives the whole thing as its first parameter and
# `undefined` as its second.
REDACT = """
({placeholder, secrets}) => {
  const hit = (v) => v && (v.startsWith('Bearer ') || secrets.some(s => s && v.includes(s)));
  for (const el of document.querySelectorAll('input, textarea')) {
    if (hit(el.value)) el.value = placeholder;
    if (el.type === 'password') el.value = placeholder;
  }
}
"""


def capture(page: Page, client_url: str, shot: Shot) -> Path:
    # (!!) Not `networkidle`. The client holds a websocket open for as long as
    # it is on screen, so the network is never idle and every navigation would
    # wait out its timeout. What says the page is ready is its own content,
    # which is what `ready` names.
    page.goto(client_url.rstrip("/") + shot.path, wait_until="domcontentloaded")
    page.wait_for_selector(shot.ready, timeout=15_000)
    # The tables fade in. Without this the capture catches them half opaque.
    page.wait_for_timeout(600)
    if shot.click:
        page.locator(shot.click).first.click()
        page.wait_for_timeout(600)
    if shot.scroll_to:
        page.locator(shot.scroll_to).first.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
    page.evaluate(
        REDACT,
        {"placeholder": "Bearer <the shared secret>", "secrets": secrets()},
    )
    # Read the page back and refuse to photograph it if anything got through.
    # A screenshot is committed and pushed, so a leak here is a leak in public,
    # and a silent one.
    leaked = page.evaluate(
        "(secrets) => [...document.querySelectorAll('input, textarea')]"
        ".some(el => secrets.some(s => s && el.value && el.value.includes(s)))",
        secrets(),
    )
    if leaked:
        raise RuntimeError(
            f"a secret is still on screen at {shot.path}, refusing to capture"
        )
    target = IMG_DIR / f"{shot.name}.png"
    if shot.crop:
        page.locator(shot.crop).first.screenshot(path=target)
    else:
        page.screenshot(path=target)
    return target


def main() -> int:
    api_url = required("DSW_API_URL")
    client_url = required("DSW_CLIENT_URL")
    minted = api(
        api_url,
        "/tokens",
        {"email": required("DSW_EMAIL"), "password": required("DSW_PASSWORD")},
    )
    token = minted["token"]
    project_uuid = find_project(api_url, token, PROJECT_NAME)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    # What the client writes itself once a human logs in. Written before the
    # first navigation, so the client is signed in on its very first paint and
    # never renders the login screen.
    #
    # (!!) `expiresAt` is not decoration. Without it the client treats the
    # session as expired and bounces every route back to the login screen,
    # which reads exactly like a wrong token.
    session = json.dumps(
        {
            "token": {"token": token, "expiresAt": minted["expiresAt"]},
            "sidebarCollapsed": False,
            "rightPanelCollapsed": True,
            "fullscreen": False,
            "apiUrl": api_url,
            "v9": True,
        }
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=SCALE, locale="en-GB"
        )
        # json.dumps twice: once for the value the client reads, once to write
        # that value into the script as a JavaScript string literal.
        context.add_init_script(
            f"window.localStorage.setItem('session/wizard', {json.dumps(session)});"
        )
        page = context.new_page()
        for shot in shots(project_uuid):
            try:
                target = capture(page, client_url, shot)
            except Exception as error:  # noqa: BLE001 - report and keep going
                print(f"FAIL {shot.name:<26} {type(error).__name__}: {error}")
                continue
            size = target.stat().st_size // 1024
            print(f"ok   {shot.name:<26} {size} KB  {shot.description}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
