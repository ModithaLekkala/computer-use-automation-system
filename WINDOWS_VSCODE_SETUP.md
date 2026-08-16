# Windows + VS Code Setup

1. Unzip the project.
2. Open VS Code.
3. Select **File -> Open Folder** and choose `interface-ai-computer-use-automation`.
4. Open **Terminal -> New Terminal**.
5. Run:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
playwright install chromium
```

Terminal 1:

```powershell
python -m demo_app.app
```

Terminal 2:

```powershell
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=10042
```

Then test the business outcome:

```powershell
python -m src.cli replay --artifact artifacts/lookup_member_balance.json --input member_id=99999
```

Then test local discovery:

```powershell
python -m src.cli discover --goal "Look up member 10042 and read their current savings balance" --target http://127.0.0.1:8000 --planner mock --artifact artifacts/lookup_member_balance.json
```
