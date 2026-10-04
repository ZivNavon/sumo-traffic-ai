"""Pure preparation tests; no SUMO, no subprocesses and no model training."""
import unittest,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
import matrix
from demand import scale
class PreparationTests(unittest.TestCase):
    def test_scale_changes_only_counts_within_phase_and_route(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'input.xml';root=ET.Element('routes')
            for i in range(8):
                v=ET.SubElement(root,'vehicle',id=str(i),depart=str(i*10));ET.SubElement(v,'route',edges='A B')
            ET.ElementTree(root).write(source)
            for factor,expected in [(.75,6),(1.25,10)]:
                target=Path(folder)/f'{factor}.xml';scale(source,target,factor,701,'balanced')
                items=ET.parse(target).getroot().findall('vehicle')
                self.assertEqual(len(items),expected);self.assertEqual(len({x.get('id') for x in items}),expected)
                self.assertTrue(all(x.find('route').get('edges')=='A B' for x in items))
                self.assertTrue(all(0<=float(x.get('depart'))<1200 for x in items))
    def test_validation_ids_unique(self):
        arm=dict(id='A-balanced-dqn-current-r1',scenario='balanced',algorithm='dqn',variant='current',checkpoints=[500,750,1000],import_pending=False)
        jobs=matrix.validation([arm],dict(validation_seeds=list(range(601,611))))
        self.assertEqual(len(jobs),30);self.assertEqual(len({j['id'] for j in jobs}),30)
        self.assertTrue(all('test' not in j['id'] for j in jobs))
    def test_joint_selection_tie_chooses_earliest(self):
        arm=dict(id='a',family='A',scenario='balanced',checkpoints=[500,750,1000])
        with patch.object(matrix,'score',return_value=10),patch.object(matrix,'baseline_mean',return_value=20),patch.object(matrix,'sha',return_value='hash'):
            selected=matrix.select([arm],{})['a']
        self.assertEqual(selected['episode'],500);self.assertEqual(selected['joint']['episode'],500)
    def test_joint_zero_denominator_blocked(self):
        arm=dict(id='a',family='A',scenario='balanced',checkpoints=[500,750,1000])
        with patch.object(matrix,'score',return_value=10),patch.object(matrix,'baseline_mean',return_value=0),patch.object(matrix,'sha',return_value='hash'):
            selected=matrix.select([arm],{})['a']
        self.assertIn('blocked',selected['joint'])
    def test_huber_and_advantage_transform_compile_without_training(self):
        import worker,variants
        worker.initialize(Path(__file__).parent/'campaign')
        td,ta,ai,ac,torch,np=[getattr(worker,k) for k in ['td','ta','ai','ac','torch','np']]
        variants.install(dict(variant='huber',algorithm='dqn'),td,ta,ai,ac,torch,np)
        self.assertIn('huber_loss',td.DQNAgent.train_step.__code__.co_names)
        self.assertIn('_record_update',td.DQNAgent.train_step.__code__.co_names)
        variants.install(dict(variant='normalized_advantage',algorithm='a2c'),td,ta,ai,ac,torch,np)
        self.assertIn('std',ta.update.__code__.co_names)
if __name__=='__main__':unittest.main()
