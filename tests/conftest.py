import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from research.db import initialize
from research.paths import now

@pytest.fixture(autouse=True)
def isolated_logs(tmp_path,monkeypatch):
    import research.pipeline as pipeline
    monkeypatch.setattr(pipeline,'DATA',tmp_path)

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'database/research.db'; initialize(path); return path

@pytest.fixture
def doc():
    return {'title':'TEST_DATA AML board internal control','jurisdiction':'United States','institution':'TEST_DATA institution','publication_date':now().date().isoformat(),'source_type':'Enforcement','source_tier':1,'source_url':'https://example.com/TEST_DATA/one','summary':'TEST_DATA: synthetic mock for tests only','verification_status':'VERIFIED','components':{'A':25,'B':20,'C':15,'D':15,'E':15},'score_evidence':{k:'TEST_DATA evidence' for k in 'ABCDE'},'evidence':'TEST_DATA — not a legal source'}
