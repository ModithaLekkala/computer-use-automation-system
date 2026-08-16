from __future__ import annotations

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
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
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={},
    )


@app.post("/member/search", response_class=HTMLResponse)
def search(
    request: Request,
    member_id: str = Form(...),
):
    member = MEMBERS.get(member_id)

    return templates.TemplateResponse(
        request=request,
        name="member.html",
        context={
            "member_id": member_id,
            "member": member,
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        "demo_app.app:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )