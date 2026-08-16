from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import uvicorn
from src.escalation.manager import registry
app=FastAPI(title="Minimal Operator Console")
@app.get("/", response_class=HTMLResponse)
def home():
    rows="".join(f"<tr><td>{x['run_id']}</td><td>{x['goal_or_capability']}</td><td>{x['reason']}</td><td>{x['state']}</td><td>{x['owner']}</td></tr>" for x in registry.all()) or '<tr><td colspan="5">No active interventions.</td></tr>'
    return f"<html><body style='font-family:Arial;margin:40px'><h1>Automation Intervention Queue</h1><table border='1' cellpadding='8'><tr><th>Run</th><th>Goal/Capability</th><th>Reason</th><th>State</th><th>Owner</th></tr>{rows}</table></body></html>"
@app.post("/interventions/{run_id}/take-control")
def take(run_id:str):
    if not registry.get(run_id): raise HTTPException(404,"Unknown run")
    return registry.take_control(run_id)
@app.post("/interventions/{run_id}/resume")
def resume(run_id:str):
    if not registry.get(run_id): raise HTTPException(404,"Unknown run")
    return registry.resume(run_id)
if __name__=="__main__": uvicorn.run("src.escalation.operator_app:app",host="127.0.0.1",port=8001)
