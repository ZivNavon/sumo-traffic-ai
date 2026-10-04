"""Raw comparison export; training and demand variation are kept separate."""
import csv,statistics,collections,json
from pathlib import Path
from worker import read_json,write_json,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign';OUT=ROOT.parents[1]/'deliverables/final-experiments-20260912'
METRICS=['avg_waiting_time','avg_travel_time','avg_stops_per_vehicle','avg_queue_length','avg_pedestrian_waiting_time']
def csvwrite(path,rows):
    if not rows:return
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def analyze():
    OUT.mkdir(parents=True,exist_ok=True);rows=[];groups=collections.defaultdict(list)
    for f in (RUN/'completed').glob('test-*.json'):
        data=read_json(f);t=data['task'];identifier=t.get('model_key',t['algorithm']+str(t.get('duration','')))
        row=dict(task_id=t['id'],model=identifier,algorithm=t['algorithm'],scenario=t['scenario'],load=t['load'],seed=t['seed'],comparison=t.get('comparison','primary'),weights=data['weight_sha256'],**{k:data['summary'][k] for k in METRICS},teleports=data['teleports'],unfinished=data['unfinished_vehicles'],wall_seconds=data['wall_elapsed_s'])
        rows.append(row);groups[(identifier,t['scenario'],t['load'],row['comparison'])].append(row)
    csvwrite(OUT/'per-demand.csv',rows)
    summaries=[];bytraining=collections.defaultdict(list)
    for key,values in sorted(groups.items()):
        row=dict(zip(['model','scenario','load','comparison'],key));row['demand_count']=len(values)
        for metric in METRICS:
            v=[r[metric] for r in values];row[metric+'_mean']=statistics.mean(v);row[metric+'_demand_sd']=statistics.stdev(v) if len(v)>1 else None
        summaries.append(row)
        family=key[0].rsplit('-r',1)[0];bytraining[(family,*key[1:])].append(row)
    csvwrite(OUT/'per-training.csv',summaries)
    variation=[]
    for key,values in sorted(bytraining.items()):
        if len(values)<2:continue
        row=dict(zip(['model_family','scenario','load','comparison'],key));row['training_count']=len(values)
        for metric in METRICS:
            v=[r[metric+'_mean'] for r in values];row[metric+'_mean_of_training_means']=statistics.mean(v);row[metric+'_between_training_sd']=statistics.stdev(v)
        variation.append(row)
    csvwrite(OUT/'between-training.csv',variation)
    baselines={(r['scenario'],r['load'],r['seed'],r['model']):r for r in rows if r['algorithm'] in ['timer','script','fixed'] and r['comparison']=='primary'}
    paired=[]
    for r in rows:
        if r['algorithm'] not in ['dqn','a2c']:continue
        for b in ['timer30','script30','fixed30']:
            base=baselines.get((r['scenario'],r['load'],r['seed'],b))
            if base:paired.append(dict(task_id=r['task_id'],baseline=b,**{k+'_difference':r[k]-base[k] for k in METRICS}))
    csvwrite(OUT/'paired-differences.csv',paired)
    decisions=[]
    for row in rows:
        if row['algorithm'] not in ['dqn','a2c']:continue
        path=RUN/'evaluations'/row['task_id']/'decisions.jsonl'
        counts=collections.Counter();entropy=[];probabilities=[];changed=0;total=0
        with path.open(encoding='utf-8') as f:
            for line in f:
                event=json.loads(line);total+=1;counts[event['proposed']]+=1;changed+=bool(event['changed'])
                if event.get('entropy') is not None:entropy.append(event['entropy']);probabilities.append(event['scores'])
        d=dict(task_id=row['task_id'],proposed_action_counts=json.dumps(dict(counts)),decisions=total,safety_changes=changed,mean_entropy=statistics.mean(entropy) if entropy else None)
        for i,duration in enumerate([20,30,40,50,60]):d[f'mean_probability_{duration}']=statistics.mean(v[i] for v in probabilities) if probabilities else None
        decisions.append(d)
    csvwrite(OUT/'decision-diagnostics.csv',decisions)
    failures=[];recovered=[]
    for f in (RUN/'failed').glob('*.json'):
        record=dict(id=f.stem,**read_json(f))
        completion=RUN/'completed'/f.name
        if completion.exists() and read_json(completion).get('status')=='passed':
            recovered.append(dict(record,resolution='A successful completion record now exists; original failure retained for provenance'))
        else:failures.append(record)
    write_json(OUT/'failures.json',failures)
    write_json(OUT/'recovered-failures.json',recovered)
    lines=['# תוצאות הניסוי','',f'נאספו {len(rows)} הערכות בדיקה. נותרו {len(failures)} משימות עם רישום כישלון או חסימה ללא השלמה מוצלחת. נמצאו {len(recovered)} רישומי כישלון היסטוריים של משימות שהושלמו בהמשך; הם נשמרו בנפרד.','',
      'הטבלה מציגה כל אימון בנפרד. שונות בין ביקושים ושונות בין ממוצעי אימונים מופיעות בקובצי CSV נפרדים. הפרש שלילי בהמתנה מציין שיפור לעומת הבסיס. אין להסיק סיבתיות או אופטימליות.', '',
      '| מודל | תרחיש | עומס | סוג בחירה | ביקושים | המתנת רכב (שניות) |', '|---|---|---|---|---:|---:|']
    for r in summaries:lines.append(f"| {r['model']} | {r['scenario']} | {r['load']} | {r['comparison']} | {r['demand_count']} | {r['avg_waiting_time_mean']:.3f} |")
    (OUT/'report-he.md').write_text('\n'.join(lines),encoding='utf-8')
    write_json(OUT/'artifact-hashes.json',{f.name:sha(f) for f in OUT.iterdir() if f.is_file() and f.name!='artifact-hashes.json'})
if __name__=='__main__':analyze()
