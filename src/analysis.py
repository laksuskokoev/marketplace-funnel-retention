"""Funnel, retention, cohorts and segmentation for a synthetic e-commerce event log."""
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'events_synthetic.csv'
STAGES = ['signup', 'view_item', 'add_to_cart', 'begin_checkout', 'purchase']
OBSERVATION_END = pd.Timestamp('2026-10-21 23:59:59')

def load_events(path=DATA):
    df = pd.read_csv(path, parse_dates=['event_time'])
    required = {'user_id','event_time','event_name','channel','device','revenue'}
    if not required.issubset(df.columns):
        raise ValueError('Missing columns: '+str(required-set(df.columns)))
    if df.duplicated(['user_id','event_time','event_name']).any():
        raise ValueError('Duplicate user/event/timestamp rows')
    return df

def user_base(df):
    signups = df.loc[df.event_name=='signup', ['user_id','event_time','channel','device']].copy()
    if signups.user_id.duplicated().any():
        raise ValueError('More than one signup per user')
    return signups.rename(columns={'event_time':'signup_time'})

def funnel(df):
    """Unique users completing each ordered step within 7 days of signup."""
    base=user_base(df).set_index('user_id')
    eligible=df.merge(base[['signup_time']],left_on='user_id',right_index=True)
    eligible=eligible[(eligible.event_time>=eligible.signup_time) &
                      (eligible.event_time < eligible.signup_time+pd.Timedelta(days=7))]
    # Require strictly ordered timestamps, not just event presence.
    reached=pd.Series(True,index=base.index)
    earliest=base.signup_time.copy()
    counts=[]
    for ix,stage in enumerate(STAGES):
        if ix==0:
            counts.append(int(len(base)))
            continue
        sub=eligible[eligible.event_name==stage][['user_id','event_time']]
        sub=sub.merge(earliest.rename('last_time'),left_on='user_id',right_index=True)
        sub=sub[sub.event_time>sub.last_time]
        first=sub.groupby('user_id').event_time.min()
        reached=reached & reached.index.isin(first.index)
        earliest=first.reindex(base.index)
        counts.append(int(reached.sum()))
    out=pd.DataFrame({'stage':STAGES,'users':counts})
    out['share_of_signups']=out.users / counts[0]
    out['step_conversion']=out.users / out.users.shift(1)
    out.loc[0,'step_conversion']=1.0
    return out

def retention(df, days=(7,14,30)):
    """Day-N retention: any activity in [signup+N, signup+N+1 days). Matured users only."""
    base=user_base(df)
    actions=df[df.event_name!='signup'][['user_id','event_time']]
    users=base[['user_id','signup_time','channel']]
    merged=actions.merge(users,on='user_id')
    delta=(merged.event_time-merged.signup_time).dt.total_seconds()/86400
    results=[]
    for d in days:
        mature=users[users.signup_time+pd.Timedelta(days=d+1)<=OBSERVATION_END]
        active=set(merged.loc[(delta>=d)&(delta<d+1),'user_id'])
        results.append({'day':d,'eligible_users':int(len(mature)),
                        'retained_users':int(mature.user_id.isin(active).sum()),
                        'retention_rate':float(mature.user_id.isin(active).mean()) if len(mature) else None})
    return pd.DataFrame(results)

def weekly_cohorts(df):
    """Weekly signup cohorts and week 1/2/3 activity, denominator restricted to mature cohorts."""
    base=user_base(df)
    base['cohort_week']=base.signup_time.dt.to_period('W-SUN').dt.start_time
    visits=df[df.event_name!='signup'][['user_id','event_time']].merge(base[['user_id','signup_time','cohort_week']],on='user_id')
    age=(visits.event_time-visits.signup_time).dt.total_seconds()/86400
    visits['week_age']=(age//7).astype(int)
    result=[]
    for week,group in base.groupby('cohort_week'):
        row={'cohort_week':week.strftime('%Y-%m-%d'), 'users':int(len(group))}
        for k in (1,2,3):
            eligible=group[group.signup_time+pd.Timedelta(days=7*(k+1))<=OBSERVATION_END]
            ids=set(visits[(visits.cohort_week==week)&(visits.week_age==k)].user_id)
            row[f'W{k}_eligible']=int(len(eligible))
            row[f'W{k}_retention']=float(eligible.user_id.isin(ids).mean()) if len(eligible) else None
        result.append(row)
    return pd.DataFrame(result)

def channel_metrics(df):
    base=user_base(df)
    purchases=df[df.event_name=='purchase'].groupby('user_id').agg(orders=('event_name','size'), revenue=('revenue','sum'))
    u=base.join(purchases,on='user_id').fillna({'orders':0,'revenue':0})
    u['purchased']=u.orders>0
    return u.groupby('channel').agg(users=('user_id','nunique'),buyers=('purchased','sum'),orders=('orders','sum'),revenue=('revenue','sum')).assign(conversion=lambda t:t.buyers/t.users,arpu=lambda t:t.revenue/t.users).reset_index()

def run():
    df=load_events(); f=funnel(df); r=retention(df); c=weekly_cohorts(df); seg=channel_metrics(df)
    (ROOT/'reports').mkdir(exist_ok=True);(ROOT/'figures').mkdir(exist_ok=True)
    for name,table in [('funnel',f),('retention',r),('cohorts',c),('channels',seg)]:
        table.to_csv(ROOT/'reports'/f'{name}.csv',index=False)
    fig,ax=plt.subplots(figsize=(9,4.5))
    ax.bar(f.stage,f.share_of_signups*100)
    ax.set(ylabel='Share of registered users (%)',title='Onboarding funnel: 7-day ordered events',ylim=(0,105))
    ax.tick_params(axis='x',rotation=20)
    fig.tight_layout();fig.savefig(ROOT/'figures'/'funnel.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(7,4))
    ax.bar(r.day.astype(str),r.retention_rate*100)
    ax.set(xlabel='Day after signup',ylabel='Retention (%)',title='Exact-day retention (matured cohorts only)')
    fig.tight_layout();fig.savefig(ROOT/'figures'/'retention.png',dpi=160);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4))
    ax.bar(seg.channel,seg.conversion*100)
    ax.set(ylabel='Purchased users (%)',title='Purchase conversion by acquisition channel')
    fig.tight_layout();fig.savefig(ROOT/'figures'/'channels.png',dpi=160);plt.close(fig)
    summary={'synthetic_data':True,'users':int(df.user_id.nunique()),'events':int(len(df)),
             'signup_to_purchase_conversion_7d':float(f.iloc[-1].share_of_signups),
             'largest_funnel_loss_stage':str(f.iloc[1:].loc[(1-f.iloc[1:].step_conversion).idxmax(),'stage']),
             'day7_retention':float(r.loc[r.day==7,'retention_rate'].iloc[0]),
             'observation_end':str(OBSERVATION_END)}
    (ROOT/'reports'/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(summary,indent=2));print('\nFUNNEL\n',f.to_string(index=False));print('\nCHANNELS\n',seg.to_string(index=False));print('\nRETENTION\n',r.to_string(index=False))
    return summary

if __name__=='__main__':
    run()
