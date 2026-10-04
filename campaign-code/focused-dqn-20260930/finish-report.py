"""Finish descriptive traffic-response and metric-cost prose from audited CSVs.

No training, simulation, model selection, or test exclusions are changed.
Wait for the primary audit to complete, within the same absolute budget.
"""
import csv,json,time,hashlib,statistics as st
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def load(name):
    with (ROOT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    clock=read(ROOT/'clock.json')
    while time.time()<clock['final_deadline']-120:
        if (ROOT/'failure.json').exists():return
        state=read(ROOT/'status.json') if (ROOT/'status.json').exists() else {}
        if state.get('stage')=='complete':break
        time.sleep(30)
    else:return
    assert read(ROOT/'verification.json')['status']=='passed'
    groups=defaultdict(list)
    for row in load('action-queue-bins.csv'):groups[(row['model'],row['load'],row['junction'],row['phase'])].append(row)
    responses=[]
    for (model,load_name,junction,phase),rows in sorted(groups.items()):
        # Minimum cell size is a descriptive display rule, not a significance test.
        eligible=sorted([r for r in rows if int(r['n'])>=30],key=lambda r:int(r['queue_bin']))
        enough=len(eligible)>=2
        low,high=(eligible[0],eligible[-1]) if enough else (None,None)
        responses.append(dict(model=model,load=load_name,junction=junction,phase=phase,eligible_bins=len(eligible),min_bin_decisions=30,
            low_bin=low['queue_bin'] if enough else '',high_bin=high['queue_bin'] if enough else '',
            low_n=low['n'] if enough else '',high_n=high['n'] if enough else '',
            proposed_high_minus_low=float(high['proposed_mean'])-float(low['proposed_mean']) if enough else '',
            applied_high_minus_low=float(high['applied_mean'])-float(low['applied_mean']) if enough else ''))
    if responses:
        with (ROOT/'action-response.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(responses[0]));w.writeheader();w.writerows(responses)
    lines=['','ניתוח הקשר לתנועה והמחיר במדדים האחרים:','',
      'לכל מודל, עומס, צומת ומופע הושוו ממוצעי משך הירוק בין קבוצת התור הנמוכה והגבוהה ביותר שבהן לפחות 30 החלטות. קבוצות התור מבוססות על סכום ארבעת רכיבי התור המנורמלים בקלט: 0, עד 0.5, עד 1 ומעל 1. רף 30 הוא כלל הצגה תיאורי, ולא מבחן מובהקות. ההשוואה בתוך אותו צומת ומופע מצמצמת ערבוב בין מופעים, אך עדיין מושפעת מזמן היום ומשאר רכיבי הקלט.']
    bymodel=defaultdict(list)
    for r in responses:bymodel[(r['model'],r['load'])].append(r)
    for (model,load_name),rows in sorted(bymodel.items()):
        valid=[r for r in rows if r['proposed_high_minus_low']!='']
        changes=[r['proposed_high_minus_low'] for r in valid]
        if changes:
            lines.append(f'{model}, עומס {load_name}: {len(valid)}/{len(rows)} קבוצות צומת–מופע ניתנות להשוואה. הפרש ממוצע המשך המוצע בין תור גבוה לנמוך נע בין {min(changes):+.2f} ל־{max(changes):+.2f} שניות. זהו קשר מדוד בתנאים שנצפו, ללא טענה לסיבתיות. פירוט המשכים המיושמים נשמר ב־action-response.csv.')
        else:lines.append(f'{model}, עומס {load_name}: אין שתי קבוצות תור בעלות 30 החלטות באותו צומת ומופע; אין די כיסוי לבדיקה זו.')
    labels={'avg_pedestrian_waiting_time':'proxy הולכי הרגל [שניות]','avg_travel_time':'זמן נסיעה [שניות]','avg_queue_length':'תור ממוצע [רכבים]','max_queue_length':'תור מרבי בגישה [רכבים]','avg_stops_per_vehicle':'עצירות לרכב'}
    costs=defaultdict(list)
    for r in load('paired-comparisons.csv'):
        if r['metric'] in labels:costs[(r['arm'],r['load'],'DQN המקורי' if r['reference'].startswith('current-') else 'הטיימר המכויל',r['metric'])].append(float(r['mean_difference']))
    lines+=['','הפרשים במדדים הנוספים, ממוצע של שלושת האימונים. סימן חיובי מציין עלייה במדד:','', '| חלופה | עומס | קו בסיס | מדד | הפרש ממוצע | SD בין הפרשי האימונים |','|---|---|---|---|---:|---:|']
    for (arm,load_name,reference,metric),values in sorted(costs.items()):
        assert len(values)==3
        lines.append(f'| {arm} | {load_name} | {reference} | {labels[metric]} | {st.mean(values):+.3f} | {st.stdev(values):.3f} |')
    supplement='\n'.join(lines)+'\n'
    (ROOT/'action-response-he.md').write_text(supplement,encoding='utf-8')
    report=ROOT/'report-he.md';marker='ניתוח הקשר לתנועה והמחיר במדדים האחרים:'
    existing=report.read_text(encoding='utf-8')
    if marker not in existing:report.write_text(existing+supplement,encoding='utf-8')
    (ROOT/'report-finished.json').write_text(json.dumps(dict(finished_at=time.time(),within_budget=time.time()<clock['final_deadline'],code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),primary_verification_sha256=hashlib.sha256((ROOT/'verification.json').read_bytes()).hexdigest()),indent=2),encoding='utf-8')
if __name__=='__main__':main()
