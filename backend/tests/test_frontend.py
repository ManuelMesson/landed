from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INDEX_JS = PROJECT_ROOT / "static" / "index.js"
INDEX_HTML = PROJECT_ROOT / "frontend" / "index.html"


def test_analyzer_page_uses_block_resume_editor() -> None:
    html = INDEX_HTML.read_text()

    assert 'id="resume-editor"' in html
    assert 'id="experience-list"' in html
    assert 'id="project-list"' in html
    assert 'id="add-experience"' in html
    assert 'id="add-project"' in html
    assert 'id="resume-skills"' in html
    assert 'id="resume-education"' in html


def test_resume_editor_parser_and_serializer_contract() -> None:
    seed_resume = """Name: Manuel Messon-Roque
Contact: Seattle, WA · manuelmesson@gmail.com
Experience:
- Barista, Compass Group (Amazon HQ), Feb 2025-Present
  - Trained new hires on fast-paced service standards
Projects:
- Landed - AI job search command center
Skills: Customer Success, Process Improvement
Education: Seattle Central College, Associate of Business, Dec 2025"""

    script = f"""
const fs = require("fs");
const vm = require("vm");

function makeElement(initial = {{}}) {{
  const element = {{
    value: "",
    innerHTML: "",
    textContent: "",
    dataset: {{}},
    style: {{}},
    children: [],
    appendChild(child) {{
      this.children.push(child);
      return child;
    }},
    addEventListener() {{}},
    setAttribute() {{}},
    querySelector() {{ return null; }},
    querySelectorAll() {{ return []; }},
    closest() {{ return null; }},
    remove() {{}},
  }};
  return Object.assign(element, initial);
}}

const elements = new Map();
[
  "#track-select",
  "#job-post",
  "#resume-editor",
  "#analyze-button",
  "#save-resume",
  "#log-job",
  "#status-line",
  "#experience-list",
  "#project-list",
  "#add-experience",
  "#add-project",
  "#ats-score",
  "#hm-score",
  "#ats-meter",
  "#hm-meter",
  "#resume-name-title",
  "#resume-contact",
  "#resume-skills",
  "#resume-education",
  "#role",
  "#date-applied",
].forEach((selector) => elements.set(selector, makeElement()));

const document = {{
  querySelector(selector) {{
    if (!elements.has(selector)) {{
      elements.set(selector, makeElement());
    }}
    return elements.get(selector);
  }},
  createElement() {{
    return makeElement();
  }},
}};

const window = {{}};
const fetch = async () => ({{
  json: async () => ([{{ id: 1, display_name: "Customer Success Specialist", base_resume: {json.dumps(seed_resume)} }}]),
}});
const setTimeout = (fn) => {{
  fn();
  return 1;
}};
const clearTimeout = () => {{}};
const setInterval = (fn) => {{
  fn();
  return 1;
}};
const clearInterval = () => {{}};

const context = {{
  console,
  document,
  window,
  fetch,
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval,
  Date,
}};

vm.createContext(context);
vm.runInContext(fs.readFileSync({json.dumps(str(INDEX_JS))}, "utf8"), context);

const parsed = context.window.LandedResumeEditor.parseResume({json.dumps(seed_resume)});

if (parsed.nameTitle !== "Manuel Messon-Roque") {{
  throw new Error("name parse failed");
}}
if (parsed.contact !== "Seattle, WA · manuelmesson@gmail.com") {{
  throw new Error("contact parse failed");
}}
if (parsed.experience.length !== 1 || parsed.experience[0].company !== "Compass Group (Amazon HQ)") {{
  throw new Error("experience parse failed");
}}
if (parsed.experience[0].bullets[0] !== "Trained new hires on fast-paced service standards") {{
  throw new Error("experience bullets parse failed");
}}
if (parsed.projects.length !== 1 || parsed.projects[0].name !== "Landed") {{
  throw new Error("project parse failed");
}}

elements.get("#resume-name-title").value = parsed.nameTitle;
elements.get("#resume-contact").value = parsed.contact;
elements.get("#resume-skills").value = parsed.skills;
elements.get("#resume-education").value = parsed.education;

function makeCard(fields) {{
  return {{
    querySelector(selector) {{
      return fields[selector] || null;
    }},
  }};
}}

elements.get("#experience-list").querySelectorAll = () => ([
  makeCard({{
    "[name='company']": {{ value: "Compass Group (Amazon HQ)" }},
    "[name='title']": {{ value: "Barista" }},
    "[name='dates']": {{ value: "Feb 2025-Present" }},
    "[name='bullets']": {{ value: "Trained new hires on fast-paced service standards\\nMaintained service quality during rushes" }},
  }}),
]);
elements.get("#project-list").querySelectorAll = () => ([
  makeCard({{
    "[name='name']": {{ value: "Landed" }},
    "[name='description']": {{ value: "AI job search command center" }},
  }}),
]);

const serialized = context.window.LandedResumeEditor.serializeResume();
if (!serialized.includes("Contact: Seattle, WA · manuelmesson@gmail.com")) {{
  throw new Error("contact serialization failed");
}}
if (!serialized.includes("- Barista, Compass Group (Amazon HQ), Feb 2025-Present")) {{
  throw new Error("experience serialization failed");
}}
if (!serialized.includes("  - Maintained service quality during rushes")) {{
  throw new Error("bullet serialization failed");
}}
if (!serialized.includes("- Landed - AI job search command center")) {{
  throw new Error("project serialization failed");
}}
"""

    subprocess.run(["node", "-e", script], check=True, cwd=PROJECT_ROOT)
