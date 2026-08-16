from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
app=FastAPI(title="LegacyBank Demo")
templates=Jinja2Templates(directory="demo_app/templates")
MEMBERS={"10042":{"name":"Avery Stone","status":"Active","savings":"4281.52","checking":"1020.20"},"10043":{"name":"Jordan Lee","status":"Active","savings":"930.17","checking":"310.42"}}
@app.get("/",response_class=HTMLResponse)
def home(request:Request): return templates.TemplateResponse("index.html",{"request":request})
@app.post("/member/search",response_class=HTMLResponse)
def search(request:Request,member_id:str=Form(...)): return templates.TemplateResponse("member.html",{"request":request,"member_id":member_id,"member":MEMBERS.get(member_id)})
if __name__=="__main__": uvicorn.run("demo_app.app:app",host="127.0.0.1",port=8000)
