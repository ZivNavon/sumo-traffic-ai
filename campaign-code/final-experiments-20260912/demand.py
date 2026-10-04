"""Deferred fresh demand generation. Never invoked during preparation."""
import sys,os,copy,random,hashlib,math,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict
from worker import read_json,write_json,sha
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'campaign'
def scale(source,target,factor,seed,scenario):
    tree=ET.parse(source);root=tree.getroot();groups=defaultdict(list)
    for item in list(root):
        if item.tag not in ('vehicle','person'):continue
        root.remove(item);t=float(item.get('depart'))
        phase=sum(t>=b for b in [600,1200,1800,2700]) if scenario=='day_cycle' else 0
        path=ET.tostring(item.find('route') if item.tag=='vehicle' else item.find('walk'),encoding='unicode')
        groups[(phase,path)].append(item)
    for key,items in sorted(groups.items()):
        ranked=sorted(items,key=lambda x:hashlib.sha256(f'{seed}:{x.get("id")}'.encode()).hexdigest())
        count=math.floor(len(items)*factor+.5)
        selected=ranked[:count] if count<=len(items) else ranked+[copy.deepcopy(ranked[i%len(ranked)]) for i in range(count-len(items))]
        for i,item in enumerate(selected):
            if i>=len(items):item.set('id',item.get('id')+'__extra')
            root.append(item)
    fixed=[x for x in root if x.tag not in ('vehicle','person')]
    mobile=sorted([x for x in root if x.tag in ('vehicle','person')],key=lambda x:(float(x.get('depart')),x.get('id')))
    root[:]=fixed+mobile;ET.indent(tree);tree.write(target,encoding='utf-8',xml_declaration=True)
def generate():
    import sumo
    os.environ['SUMO_HOME']=str(Path(sumo.__file__).parent)
    sys.path.insert(0,str(RUN/'snapshot/sim'))
    from scenarios import gen_multiseed_scenarios as g
    from scenarios import gen_directional as d
    p=read_json(RUN/'protocol.json');out=RUN/'demand';out.mkdir(exist_ok=True)
    g.SCENARIOS_DIR=str(out)
    # Directional writer derives output folder from its own __file__.
    d.__file__=str(out/'gen_directional.py')
    def rt(path,seed,period,persons=False):
        cmd=[sys.executable,g.RT,'-n',g.NET_FILE,'-r',str(path),'--seed',str(seed),'--period',str(period),'--end','1200','--fringe-factor','5']
        if persons:cmd+=['--pedestrians']
        result=subprocess.run(cmd,cwd=out,capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
    metadata=[]
    for seed in p['validation_seeds']+p['test_seeds']:
        for s in p['scenarios']:
            name=f'{s}_s{seed}';rou=out/f'{name}.rou.xml';ped=out/f'{name}.ped.xml'
            if not (out/f'{name}.ready.json').exists():
                if s in ['balanced','heavy_west','pedestrian_heavy']:
                    rt(rou,seed,2 if s=='balanced' else 6)
                    rt(ped,seed,2 if s=='pedestrian_heavy' else 6,True)
                    if s=='heavy_west':
                        # Freeze a demand-seeded Bernoulli stream before controllers run.
                        tree=ET.parse(rou);root=tree.getroot();rng=random.Random(seed+1000000)
                        for t in range(1200):
                            if rng.random()<.5:
                                v=ET.Element('vehicle',id=f'heavy_west_{t}',depart=str(t));ET.SubElement(v,'route',edges='A1B1 B1C1 C1D1');root.append(v)
                        root[:]=[x for x in root if x.tag!='vehicle']+sorted(root.findall('vehicle'),key=lambda x:(float(x.get('depart')),x.get('id')))
                        tree.write(rou,encoding='utf-8',xml_declaration=True)
                elif s in ['morning_flow','evening_flow']:d.write_scenario(name,d.S_TO_N_ROUTES if s=='morning_flow' else d.N_TO_S_ROUTES,seed)
                else:g._gen_day_cycle(name,seed)
                write_json(out/f'{name}.ready.json',dict(route=sha(rou),pedestrian=sha(ped)))
            for load in p['loads'] if seed in p['test_seeds'] else ['base']:
                paths=[]
                for ext,source in [('rou',rou),('ped',ped)]:
                    dest=out/f'{name}_{load}.{ext}.xml'
                    factor=(.75 if load.endswith('075') else 1.25) if ((ext=='rou' and load.startswith('vehicle')) or (ext=='ped' and load.startswith('pedestrian'))) else 1.
                    if factor==1:
                        import shutil
                        shutil.copy2(source,dest)
                    else:scale(source,dest,factor,seed,s)
                    root=ET.parse(dest).getroot();items=root.findall('vehicle' if ext=='rou' else 'person')
                    assert items and len({x.get('id') for x in items})==len(items)
                    assert max(float(x.get('depart')) for x in items)<(3600 if s=='day_cycle' else 1200)
                    paths.append(dict(path=str(dest.relative_to(RUN)),sha256=sha(dest),count=len(items),factor=factor))
                metadata.append(dict(scenario=s,seed=seed,load=load,files=paths))
    write_json(RUN/'demand-manifest.json',metadata)
if __name__=='__main__':raise SystemExit('Call only from the explicitly authorized scheduler')
