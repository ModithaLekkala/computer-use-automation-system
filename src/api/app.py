from pathlib import Path
from fastapi import FastAPI, HTTPException
import uvicorn
from src.capabilities.store import load_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface
app=FastAPI(title="Capability Catalog")
def available():
    out=[]
    for p in Path("artifacts").glob("*.json"):
        try: out.append((p,load_artifact(str(p))))
        except Exception: pass
    return out
@app.get("/capabilities")
def caps(): return [{"name":a.name,"description":a.description,"inputs":{k:v.model_dump() for k,v in a.inputs.items()},"outputs":{k:v.model_dump() for k,v in a.outputs.items()},"version":a.capability_version} for _,a in available()]
@app.post("/capabilities/{name}/run")
async def run(name:str,payload:dict):
    match=next(((p,a) for p,a in available() if a.name==name),None)
    if not match: raise HTTPException(404,"Capability not found")
    return await ReplayEngine(PlaywrightSurface(headless=True)).run(match[1],payload)
if __name__=="__main__": uvicorn.run("src.api.app:app",host="127.0.0.1",port=8002)
