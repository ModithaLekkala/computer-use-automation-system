from src.replay.engine import ReplayEngine
class Dummy: pass
def test_bind(): assert ReplayEngine(Dummy(),"/tmp/evidence")._bind("{{member_id}}",{"member_id":"10042"})=="10042"
