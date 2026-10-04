"""Independent reconstruction and bounded, descriptive analysis of frozen tests."""
import json,csv,math,statistics as st,time,random,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict,Counter
from worker import read_json as read,write_json as write,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
METRICS=['avg_waiting_time','avg_pedestrian_waiting_time','avg_travel_time','avg_queue_length','max_queue_length','avg_stops_per_vehicle']
def sd(x):return st.stdev(x) if len(x)>1 else 0.
def csvout(name,rows):
    if not rows:return
    with (ROOT/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def close(a,b):assert math.isclose(a,b,abs_tol=1e-9,rel_tol=1e-10),(a,b)
def main():
    started=time.time();clock=read(ROOT/'clock.json');assert started<clock['final_deadline']
    p=read(RUN/'protocol.json');gate=read(RUN/'test-gate.json')
    for name,digest in gate['hashes'].items():assert sha(RUN/name)==digest
    for name,digest in read(ROOT/'copied-source-hashes.json').items():assert sha(ROOT/name)==digest
    for name,digest in read(ROOT/'preflight.json')['hashes'].items():assert sha(ROOT/name)==digest
    tasks=read(RUN/'validation-manifest.json')+read(RUN/'test-manifest.json')
    testrows=[];actions=[];audit=[];bins=defaultdict(list);counter=Counter();failed=[]
    manifest={x['path']:x['sha256'] for d in read(RUN/'demand-manifest.json') for x in d['files']}
    for path,digest in manifest.items():assert sha(RUN/path)==digest,path
    for t in tasks:
        assert time.time()<clock['final_deadline']-30,'Analysis deadline'
        folder=RUN/'evaluations'/t['id'];r=read(folder/'result.json');assert r==read(RUN/'completed'/f'{t["id"]}.json')
        assert r['status']=='passed' and r['task']==t
        tree=ET.parse(folder/'tripinfo.xml').getroot();trips=tree.findall('tripinfo');persons=tree.findall('personinfo')
        demand=RUN/'demand'/f'{t["demand_name"]}.rou.xml';ped=RUN/'demand'/f'{t["demand_name"]}.ped.xml'
        ids=[v.get('id') for v in trips];expected=[v.get('id') for v in ET.parse(demand).getroot().findall('vehicle')]
        personids=[v.get('id') for v in persons];pexpected=[v.get('id') for v in ET.parse(ped).getroot().findall('person')]
        assert len(ids)==len(set(ids)) and set(ids)==set(expected)
        assert len(personids)==len(set(personids)) and set(personids)==set(pexpected)
        assert r['created_vehicles']==r['departed_vehicles']==r['arrived_vehicles']==len(expected) and r['unfinished_vehicles']==0
        assert not any(v.get('vaporized','') not in ('','false','0') for v in trips)
        for name,path in r['input_hashes'].items():assert sha(Path(name))==path
        if t.get('weights'):assert r['weight_sha256']==t['expected_weight_sha256']==sha(RUN/t['weights'])
        summary=r['summary'];waits=[float(v.get('waitingTime')) for v in trips]
        close(summary['avg_waiting_time'],st.mean(waits));close(summary['avg_travel_time'],st.mean(float(v.get('duration')) for v in trips));close(summary['avg_stops_per_vehicle'],st.mean(float(v.get('waitingCount',0)) for v in trips))
        count=0;qsum=0.;qmax=0;ps=0.;pn=0;pm=0.
        for line in (folder/'metric-samples.jsonl').open(encoding='utf-8'):
            s=json.loads(line);count+=1;qsum+=s['queue'][0];qmax=max(qmax,s['queue'][1]);a=s['pedestrian'][1]
            if a>0:ps+=a;pn+=1
            pm=max(pm,s['pedestrian'][2])
        assert count==r['simulation_steps'];close(summary['avg_queue_length'],qsum/count);close(summary['max_queue_length'],qmax);close(summary['avg_pedestrian_waiting_time'],ps/pn if pn else 0);close(summary['max_pedestrian_waiting_time'],pm)
        obs=read(folder/'completion-observation.json');assert obs['teleports']==r['teleports'] and obs['colliding_vehicles']==r['colliding_vehicles']
        counter['evaluations']+=1;counter['trips']+=len(trips);counter['persons']+=len(persons);counter['teleports']+=r['teleports'];counter['collision_vehicle_observations']+=r['colliding_vehicles'];counter['metric_samples']+=count
        audit.append(dict(task=t['id'],split=t['split'],vehicles=len(ids),persons=len(personids),unfinished=0,teleports=r['teleports'],colliding_vehicles=r['colliding_vehicles'],xml_and_samples_verified=True,weight_sha256=r['weight_sha256']))
        if t['split']!='test':continue
        row=dict(task=t['id'],model=t['model'],family=t['family'],repetition=t['repetition'],seed=t['seed'],load=t['load'],**{m:summary[m] for m in METRICS},unfinished=0,teleports=r['teleports'],colliding_vehicles=r['colliding_vehicles'],wall_seconds=r['wall_elapsed_s'])
        testrows.append(row);proposed=Counter();applied=Counter();changed=0;total=0;group=defaultdict(list)
        for line in (folder/'decisions.jsonl').open(encoding='utf-8'):
            d=json.loads(line);proposed[d['proposed']]+=1;applied[d['applied']]+=1;changed+=bool(d['changed']);total+=1
            if t['algorithm']=='dqn':
                scores=d['scores'];action=max(range(len(scores)),key=lambda i:scores[i]);assert [20,30,40,50,60][action]==d['proposed'],'Greedy argmax mismatch'
                assert d['raw_vector']==d['vector'],'Unexpected input mask'
                q=sum(d['raw_vector'][:4]);bucket=0 if q==0 else 1 if q<=.5 else 2 if q<=1 else 3
                key=(t['model'],t['load'],d['junction'],d['phase'],bucket)
                bins[key].append((d['proposed'],d['applied']));group[(d['junction'],d['phase'])].append(d['proposed'])
        actions.append(dict(model=t['model'],seed=t['seed'],load=t['load'],decisions=total,safety_changes=changed,proposed_counts=json.dumps(proposed),applied_counts=json.dumps(applied),junction_phase_groups_with_multiple_proposals=sum(len(set(x))>1 for x in group.values())))
    # Verify every complete new training, including epsilon schedule, demand order, cp hashes and fresh initialization.
    scope=read(ROOT/'scope.json');new=[t for t in read(RUN/'training-manifest.json') if t['variant'] in scope['arms']]
    training=[]
    for t in new:
        folder=RUN/'training'/t['id'];rng=random.Random(p['demand_schedule_seed']);elapsed=0.
        initial=read(folder/'initial.json');assert initial['fresh_initialization'] and initial['learning_seed']==t['learning_seed'] and initial['sha256']==sha(folder/'initial.pt')
        for ep in range(1,1001):
            row=read(folder/'episodes'/f'{ep:04d}.json');assert row['demand_seed']==rng.choice(p['train_seeds']) and row['sumo_seed']==p['sumo_seed'] and row['learning_seed']==t['learning_seed']
            settings=p['arms'][t['variant']];close(row['learning_rate'],settings['LR']);close(row['epsilon'],max(.05,settings['EPS_DECAY']**ep));elapsed+=row['wall_seconds']
        for ep in p['checkpoints']:assert sha(folder/f'checkpoint-{ep}.pt')==read(folder/f'checkpoint-{ep}.json')['sha256']
        training.append(dict(model=t['id'],learning_seed=t['learning_seed'],episodes=1000,raw_compute_wall_seconds=elapsed,initial_sha256=initial['sha256'],verified=True))
    for arm in scope['arms']:
        assert len({r['initial_sha256'] for r in training if r['model'].startswith(arm+'-')})==3,'Initializations not independent'
    models=defaultdict(list)
    for row in testrows:models[(row['model'],row['load'])].append(row)
    per=[]
    for (model,load),rows in models.items():
        assert len(rows)==20 and {r['seed'] for r in rows}==set(p['test_seeds'])
        x=dict(model=model,family=rows[0]['family'],repetition=rows[0]['repetition'],load=load,demands=len(rows))
        for m in METRICS:x[m+'_mean']=st.mean(r[m] for r in rows);x[m+'_demand_sd']=sd([r[m] for r in rows])
        x.update(teleports=sum(r['teleports'] for r in rows),colliding_vehicles=sum(r['colliding_vehicles'] for r in rows),unfinished=0);per.append(x)
    family=[];families=['current']+scope['arms']+['TIMER','calibrated']
    for load in p['loads']:
        for f in families:
            rows=[x for x in per if x['load']==load and x['family']==f]
            assert len(rows)==(3 if f in ['current']+scope['arms'] else 1)
            x=dict(family=f,load=load,trainings=len(rows) if len(rows)>1 else 0,demands=20)
            for m in METRICS:
                x[m+'_mean']=st.mean(r[m+'_mean'] for r in rows)
                x[m+'_between_training_sd']=sd([r[m+'_mean'] for r in rows]) if len(rows)>1 else None
                x[m+'_mean_within_training_demand_sd']=st.mean(r[m+'_demand_sd'] for r in rows)
            family.append(x)
    lookup={(r['model'],r['load'],r['seed']):r for r in testrows};comparisons=[]
    # Keep paired seed differences and all three training means; no pseudo-replication CI.
    for arm in scope['arms']:
        for load in p['loads']:
            for rep in range(1,4):
                for reference in [f'current-r{rep}','calibrated']:
                    for m in METRICS:
                        a=[lookup[(f'{arm}-r{rep}',load,s)][m] for s in p['test_seeds']];b=[lookup[(reference,load,s)][m] for s in p['test_seeds']];diff=[x-y for x,y in zip(a,b)]
                        comparisons.append(dict(arm=arm,repetition=rep,load=load,reference=reference,metric=m,mean_difference=st.mean(diff),paired_demand_difference_sd=sd(diff),percent_change=100*(st.mean(a)/st.mean(b)-1) if st.mean(b) else None,demands_improved=sum(x<0 for x in diff),demands=20))
    sensitivity=[]
    for load in p['loads']:
        excluded={r['seed'] for r in testrows if r['load']==load and (r['teleports'] or r['colliding_vehicles'])}
        for f in families:
            rows=[r for r in testrows if r['load']==load and r['family']==f and r['seed'] not in excluded]
            sensitivity.append(dict(load=load,family=f,excluded_seeds=json.dumps(sorted(excluded)),retained_demands=20-len(excluded),avg_waiting_time=st.mean(r['avg_waiting_time'] for r in rows) if rows else None))
    binrows=[]
    for key,vals in sorted(bins.items()):
        model,load,junction,phase,bucket=key
        binrows.append(dict(model=model,load=load,junction=junction,phase=phase,queue_bin=bucket,n=len(vals),proposed_mean=st.mean(v[0] for v in vals),applied_mean=st.mean(v[1] for v in vals),proposed_counts=json.dumps(Counter(v[0] for v in vals))))
    csvout('raw-test.csv',testrows);csvout('per-training.csv',per);csvout('family-summary.csv',family);csvout('paired-comparisons.csv',comparisons);csvout('integrity.csv',audit);csvout('training-integrity.csv',training);csvout('actions.csv',actions);csvout('action-queue-bins.csv',binrows);csvout('teleport-sensitivity.csv',sensitivity)
    write(ROOT/'verification.json',dict(status='passed',counts=dict(counter),new_training_runs=len(new),test_rows=len(testrows),gate_verified=True,source_hashes_verified=True,elapsed_seconds=time.time()-started))
    lines=['# סבב DQN ממוקד: תוצאות מדודות','',f'הושלמו {len(new)} אימונים חדשים של 1,000 פרקים, שלושה לכל חלופה שנכללה. הסבב כלל תיקוף חדש 2001–2010 ובדיקה חדשה 2101–2120. כל התצורות קיבלו אותם קובצי ביקוש. משך הסבב עד סיום הניתוח: {(time.time()-clock["started_at"])/3600:.2f} שעות.','', 'בחירת checkpoint נעשתה לפי המתנת רכב בתיקוף, עם העדפה לפרק המוקדם בתיקו. נבחר גם הטיימר המכויל מחדש מתוך 20/30/40/50/60 שניות. קצב הלמידה בחלופת lr0003 הוא 0.0003; דעיכת epsilon בחלופת eps998 היא 0.998. שאר הגדרות הלמידה, התגמול והבקרה נשמרו.','', '| עומס | תצורה | המתנת רכב [ש׳] | SD בין אימונים | SD ביקושים ממוצע | הולכי רגל proxy [ש׳] | נסיעה [ש׳] | תור ממוצע [רכבים] | עצירות לרכב |','|---|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in family:
        lines.append(f'| {r["load"]} | {r["family"]} | {r["avg_waiting_time_mean"]:.3f} | '+(f'{r["avg_waiting_time_between_training_sd"]:.3f}' if r['trainings'] else '—')+f' | {r["avg_waiting_time_mean_within_training_demand_sd"]:.3f} | {r["avg_pedestrian_waiting_time_mean"]:.3f} | {r["avg_travel_time_mean"]:.3f} | {r["avg_queue_length_mean"]:.3f} | {r["avg_stops_per_vehicle_mean"]:.3f} |')
    lines+=['','שונות בין אימונים היא סטיית התקן של שלושת ממוצעי האימון. שונות בין ביקושים חושבה בתוך כל אימון בנפרד, ולא כ־60 אימונים עצמאיים. פירוט כל אימון נמצא ב־per-training.csv. ההפרשים בכל המדדים מופיעים ב־paired-comparisons.csv; הפרש שלילי מציין ירידה במדד.','']
    conclusions=[]
    for arm in scope['arms']:
        for load in p['loads']:
            for reference,label in [('current','DQN המקורי'),('calibrated','הטיימר המכויל')]:
                rr=[r for r in comparisons if r['arm']==arm and r['load']==load and r['metric']=='avg_waiting_time' and (r['reference'].startswith('current-') if reference=='current' else r['reference']=='calibrated')]
                delta=st.mean(r['mean_difference'] for r in rr);wins=sum(r['mean_difference']<0 for r in rr)
                conclusions.append(f'בחלופת {arm}, בעומס {load}, ההפרש הממוצע מול {label} הוא {delta:+.3f} שניות המתנת רכב; {wins}/3 אימונים השיגו המתנה נמוכה יותר. סטיית התקן בין שלושת ההפרשים: {sd([r["mean_difference"] for r in rr]):.3f} שניות.')
    lines+=conclusions+['',f'כל {counter["evaluations"]} הערכות התיקוף והבדיקה נבדקו מול tripinfo.xml ודגימות המדדים. אפס רכבים ואפס הולכי רגל חסרים בפלטי ההשלמה. מספר teleports: {counter["teleports"]}; מונה תצפיות רכב בהתנגשות: {counter["collision_vehicle_observations"]}. כל האירועים נשמרו בתוצאה הראשית; teleport-sensitivity.csv מציג גם הוצאת seed משותפת לכל התצורות באותו עומס.','', 'מדד הולכי הרגל הוא ה־proxy המקורי: ממוצע חיובי לאורך הזמן של ממוצעי הצמתים. אין לפרשו כהמתנה ממוצעת של כלל האנשים. מונה התנגשות הוא סכום התצפיות שמחזיר SUMO, ואינו מספר תאונות ייחודיות.','', 'actions.csv ו־action-queue-bins.csv מציגים משכים מוצעים ומיושמים, התערבות מגבלות ופילוח תור לפי צומת ומופע. שינוי משך בין קבוצות תור הוא קשר תיאורי; אין להסיק שהעומס לבדו גרם לשינוי. כל החלטות DQN נבדקו מול argmax של ציוני הרשת.','']
    for arm in ['current']+scope['arms']:
        rows=[r for r in actions if r['model'].startswith(arm+'-')]
        varied=sum(r['junction_phase_groups_with_multiple_proposals']>0 for r in rows)
        lines.append(f'{arm}: מגוון משכים בתוך אותו צומת ומופע נמצא ב־{varied}/{len(rows)} הרצות. אין די במגוון לבדו כדי להוכיח תגובה לעומס; הפילוח המפורט שמור בטבלת קבוצות התור.')
    if scope['excluded_arms']:lines+=['',f'חלופות שהוצאו לפני תיקוף עקב תקציב הזמן: {scope["excluded_arms"]}. אין לגביהן השוואה מלאה.']
    lines+=['','פסקה מוצעת לספר, על סמך המדידות בלבד:','', 'בסבב נוסף במחזור היום נבדקו שינויי פרמטר יחיד ב־DQN, עם שלושה אימונים עצמאיים לכל חלופה שנכללה, ובחירת משקולות על תיקוף חדש לפני בדיקה ב־20 ביקושים חדשים בשתי רמות עומס. '+ ' '.join(conclusions)+' התוצאות תלויות בפרוטוקול ובביקושים שנבדקו; אין בניסוי זה בידוד של המנגנון שמסביר את ההבדלים. פשרות בשירות הולכי הרגל, זמן נסיעה, תורים ועצירות מוצגות לצד המתנת הרכב.']
    (ROOT/'report-he.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':main()
