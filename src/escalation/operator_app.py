from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from src.escalation.manager import registry


def build_operator_app() -> FastAPI:
    app = FastAPI(title="Minimal Operator Console")

    @app.get("/", response_class=HTMLResponse)
    def home():
        rows = []
        for item in registry.all():
            run_id = item["run_id"]
            rows.append(
                f"""
                <tr>
                  <td>{run_id}</td>
                  <td>{item['goal_or_capability']}</td>
                  <td>{item['reason']}</td>
                  <td>{item['state']}</td>
                  <td>{item['owner']}</td>
                  <td>
                    <button onclick="post('/interventions/{run_id}/take-control')">
                      Take Control
                    </button>
                    <button onclick="post('/interventions/{run_id}/resume')">
                      Resume
                    </button>
                    <button onclick="post('/interventions/{run_id}/abort')">
                      Abort
                    </button>
                  </td>
                </tr>
                """
            )

        return f"""
        <!doctype html>
        <html>
        <head>
          <title>Operator Console</title>
          <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f4f4f4; }}
            .card {{ background: white; padding: 24px; border: 1px solid #aaa; }}
            table {{ border-collapse: collapse; width: 100%; }}
            td, th {{ border: 1px solid #bbb; padding: 10px; vertical-align: top; }}
            button {{ margin-right: 6px; padding: 7px 10px; }}
          </style>
          <script>
            async function post(path) {{
              const response = await fetch(path, {{ method: 'POST' }});
              if (!response.ok) {{
                alert(await response.text());
                return;
              }}
              location.reload();
            }}
          </script>
        </head>
        <body>
          <div class="card">
            <h1>Automation Intervention Queue</h1>
            <p>
              During a handoff, click <b>Take Control</b>, operate the already-open
              Chromium window manually, then click <b>Resume</b>.
            </p>
            <table>
              <tr>
                <th>Run</th><th>Goal / Capability</th><th>Reason</th>
                <th>State</th><th>Owner</th><th>Actions</th>
              </tr>
              {''.join(rows) or '<tr><td colspan="6">No active interventions.</td></tr>'}
            </table>
          </div>
        </body>
        </html>
        """

    @app.post("/interventions/{run_id}/take-control")
    def take_control(run_id: str):
        if not registry.get(run_id):
            raise HTTPException(404, "Unknown run")
        return registry.take_control(run_id)

    @app.post("/interventions/{run_id}/resume")
    def resume(run_id: str):
        if not registry.get(run_id):
            raise HTTPException(404, "Unknown run")
        return registry.resume(run_id)

    @app.post("/interventions/{run_id}/abort")
    def abort(run_id: str):
        if not registry.get(run_id):
            raise HTTPException(404, "Unknown run")
        return registry.abort(run_id)

    return app


app = build_operator_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.escalation.operator_app:app", host="127.0.0.1", port=8001, reload=False)
