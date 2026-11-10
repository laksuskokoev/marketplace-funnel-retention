import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.analysis import load_events, funnel, retention, channel_metrics, weekly_cohorts

def test_users_and_monotone_funnel():
    data=load_events(); f=funnel(data)
    assert data.user_id.nunique()==8000
    assert f.users.is_monotonic_decreasing
    assert f.users.iloc[0]==8000

def test_retention_eligibility():
    r=retention(load_events())
    assert ((r.retention_rate>=0)&(r.retention_rate<=1)).all()
    assert r.eligible_users.is_monotonic_decreasing

def test_segment_totals():
    s=channel_metrics(load_events())
    assert s.users.sum()==8000
    assert (s.buyers<=s.users).all()

def test_cohorts():
    c=weekly_cohorts(load_events())
    assert c.users.sum()==8000
    assert ((c.W1_retention.dropna()>=0)&(c.W1_retention.dropna()<=1)).all()
