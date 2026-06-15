from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from generator.validate import validate_agent
from generator.verify import verify_generated
from meta_agent.orchestrator import ROOT, asdict_result, pipeline_from_prompt, save_proposal_from_prompt, validate_repair_generate
from meta_agent.repair import repair_agent_spec

app = FastAPI(title="Resource Agent Meta-Factory", version="0.1.0")


class PromptRequest(BaseModel):
    prompt: str = Field(..., min_length=3)
    output_path: str | None = None
    auto_repair: bool = True


class SpecPathRequest(BaseModel):
    spec_path: str
    write: bool = False


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/proposals/from-prompt")
def proposal_from_prompt(req: PromptRequest) -> dict[str, Any]:
    output_path = Path(req.output_path) if req.output_path else None
    path = save_proposal_from_prompt(req.prompt, output_path)
    return {"status": "draft", "spec_path": str(path), "yaml": yaml.safe_load(path.read_text(encoding="utf-8"))}


@app.post("/validate")
def validate(req: SpecPathRequest) -> dict[str, Any]:
    path = Path(req.spec_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Spec not found: {path}")
    errors = validate_agent(path)
    return {"ok": not errors, "errors": errors}


@app.post("/repair")
def repair(req: SpecPathRequest) -> dict[str, Any]:
    path = Path(req.spec_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Spec not found: {path}")
    result = repair_agent_spec(path, write=req.write)
    return {
        "changed": result.changed,
        "errors_before": result.errors_before,
        "errors_after": result.errors_after,
        "warnings": result.warnings,
        "repaired_yaml": result.repaired_yaml,
    }


@app.post("/generate")
def generate(req: SpecPathRequest) -> dict[str, Any]:
    path = Path(req.spec_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Spec not found: {path}")
    return asdict_result(validate_repair_generate(path, auto_repair=req.write))


@app.post("/pipeline/from-prompt")
def pipeline(req: PromptRequest) -> dict[str, Any]:
    output_path = Path(req.output_path) if req.output_path else None
    result = pipeline_from_prompt(req.prompt, output_path=output_path, auto_repair=req.auto_repair)
    return asdict_result(result)


@app.get("/verify")
def verify() -> dict[str, Any]:
    errors = verify_generated(ROOT / "agents" / "generated")
    return {"ok": not errors, "errors": errors}
