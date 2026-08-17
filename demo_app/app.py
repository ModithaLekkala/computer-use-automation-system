from __future__ import annotations

from collections import defaultdict

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="LegacyBank Demo")
templates = Jinja2Templates(directory="demo_app/templates")

MEMBERS = {
    "10042": {
        "name": "Avery Stone",
        "status": "Active",
        "savings": "4281.52",
        "checking": "1020.20",
    },
    "10043": {
        "name": "Jordan Lee",
        "status": "Active",
        "savings": "930.17",
        "checking": "310.42",
    },
    # 10044 triggers a manual-review handoff before showing the profile.
    "10044": {
        "name": "Taylor Morgan",
        "status": "Manual Review",
        "savings": "2024.11",
        "checking": "802.50",
    },
    # 10045 triggers one transient load before succeeding on retry.
    "10045": {
        "name": "Casey Rivera",
        "status": "Active",
        "savings": "1575.25",
        "checking": "455.40",
    },
}

SEARCH_ATTEMPTS: dict[str, int] = defaultdict(int)


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.post("/member/search", response_class=HTMLResponse)
def search(request: Request, member_id: str = Form(...)):
    member_id = member_id.strip()
    member = MEMBERS.get(member_id)

    if member_id == "10044" and member:
        return templates.TemplateResponse(
            request=request,
            name="manual_review.html",
            context={"member_id": member_id, "member": member},
        )

    if member_id == "10045" and member:
        SEARCH_ATTEMPTS[member_id] += 1
        if SEARCH_ATTEMPTS[member_id] == 1:
            return templates.TemplateResponse(
                request=request,
                name="transient.html",
                context={"member_id": member_id},
            )

    return templates.TemplateResponse(
        request=request,
        name="member.html",
        context={"member_id": member_id, "member": member},
    )


@app.post("/member/manual-review/continue", response_class=HTMLResponse)
def continue_manual_review(request: Request, member_id: str = Form(...)):
    member = MEMBERS.get(member_id)
    return templates.TemplateResponse(
        request=request,
        name="member.html",
        context={"member_id": member_id, "member": member},
    )


@app.post("/member/retry", response_class=HTMLResponse)
def retry(request: Request, member_id: str = Form(...)):
    member = MEMBERS.get(member_id)
    return templates.TemplateResponse(
        request=request,
        name="member.html",
        context={"member_id": member_id, "member": member},
    )


@app.post("/test/reset/{member_id}")
def reset_test_state(member_id: str):
    SEARCH_ATTEMPTS[member_id] = 0
    return {"ok": True}


if __name__ == "__main__":
    uvicorn.run("demo_app.app:app", host="127.0.0.1", port=8000, reload=False)
