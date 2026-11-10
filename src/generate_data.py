"""Generate a reproducible SYNTHETIC e-commerce event log. No real users."""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'events_synthetic.csv'
END = pd.Timestamp('2026-10-21 23:59:59')

def main(n_users=8000, seed=2026):
    rng = np.random.default_rng(seed)
    days = pd.date_range('2026-08-01', '2026-09-30', freq='D')
    weights = np.where(days.month == 8, 1.0, 1.2).astype(float)
    weights /= weights.sum()
    dates = rng.choice(days.to_numpy(), size=n_users, p=weights)
    channels = rng.choice(['organic', 'paid_search', 'social', 'referral'], size=n_users, p=[.40,.30,.20,.10])
    device = rng.choice(['mobile','desktop'], size=n_users, p=[.72,.28])
    rows=[]
    def put(uid, ts, action, channel, dev, value=0.0):
        if ts <= END:
            rows.append((uid,ts,action,channel,dev,round(float(value),2)))
    for i in range(n_users):
        uid = f'U{i+1:05d}'
        ts = pd.Timestamp(dates[i]) + pd.Timedelta(minutes=int(rng.integers(0,1440)))
        ch,dev=channels[i],device[i]
        put(uid,ts,'signup',ch,dev)
        # Sequential onboarding funnel, with a channel/device-dependent dropout
        chance = .85 if dev == 'desktop' else .78
        if rng.random()<chance:
            put(uid, ts+pd.Timedelta(minutes=3),'view_item',ch,dev)
            if rng.random()<(.54 if ch == 'organic' else .46):
                put(uid,ts+pd.Timedelta(minutes=8),'add_to_cart',ch,dev)
                if rng.random()<(.75 if dev=='desktop' else .66):
                    put(uid,ts+pd.Timedelta(minutes=12),'begin_checkout',ch,dev)
                    if rng.random()<(.69 if dev=='desktop' else .57):
                        put(uid,ts+pd.Timedelta(minutes=17),'purchase',ch,dev, rng.lognormal(4.5,.45))
        # Weekly return visits (separate from checkout conversion)
        base = {'organic':.28,'paid_search':.18,'social':.13,'referral':.33}[ch]
        for week in [1,2,3,4,5,6,7,8,9,10]:
            chance = base * (.78 ** (week-1))
            if rng.random()<chance:
                revisit = ts+pd.Timedelta(days=week*7+int(rng.integers(0,7)),hours=1)
                put(uid,revisit,'return_visit',ch,dev)
    df=pd.DataFrame(rows,columns=['user_id','event_time','event_name','channel','device','revenue'])
    df=df.sort_values(['event_time','user_id','event_name']).reset_index(drop=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    df.to_csv(OUT,index=False,date_format='%Y-%m-%d %H:%M:%S')
    print('Wrote',OUT,'rows',len(df),'users',df.user_id.nunique())

if __name__ == '__main__':
    main()
