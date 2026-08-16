from src.capabilities.store import load_artifact
def test_artifact_parses():
    a=load_artifact("artifacts/lookup_member_balance.json")
    assert a.name=="lookup_member_balance" and "member_id" in a.inputs
