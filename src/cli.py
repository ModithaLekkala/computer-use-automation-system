import argparse, asyncio
from src.agent.discovery import DiscoveryAgent
from src.agent.planners import MockPlanner, OpenAIPlanner
from src.capabilities.store import load_artifact, save_artifact
from src.replay.engine import ReplayEngine
from src.surfaces.playwright_surface import PlaywrightSurface

def parse_inputs(values):
    out={}
    for item in values:
        k,v=item.split("=",1); out[k]=v
    return out
async def do_discover(args):
    planner=OpenAIPlanner() if args.planner=="openai" else MockPlanner()
    artifact=await DiscoveryAgent(PlaywrightSurface(headless=args.headless),planner).run(args.goal,args.target)
    save_artifact(artifact,args.artifact); print(artifact.model_dump_json(indent=2))
async def do_replay(args):
    artifact=load_artifact(args.artifact)
    result=await ReplayEngine(PlaywrightSurface(headless=args.headless)).run(artifact,parse_inputs(args.input))
    print(result.model_dump_json(indent=2))
def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="command",required=True)
    d=sub.add_parser("discover"); d.add_argument("--goal",required=True); d.add_argument("--target",required=True); d.add_argument("--planner",choices=["mock","openai"],default="mock"); d.add_argument("--artifact",default="artifacts/lookup_member_balance.json"); d.add_argument("--headless",action="store_true")
    r=sub.add_parser("replay"); r.add_argument("--artifact",required=True); r.add_argument("--input",action="append",default=[]); r.add_argument("--headless",action="store_true")
    a=p.parse_args(); asyncio.run(do_discover(a) if a.command=="discover" else do_replay(a))
if __name__=="__main__": main()
