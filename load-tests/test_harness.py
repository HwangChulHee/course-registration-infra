import datetime as dt
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import bench

class HarnessTests(unittest.TestCase):
    def test_refuses_demo_database(self):
        with patch.object(bench,'sql',return_value='course_registration'):
            with self.assertRaisesRegex(RuntimeError,'Refusing'):
                bench.assert_isolated()

    def test_foreign_volume_refused_before_initialization(self):
        result=type('Result',(),{'returncode':0,'stdout':'[{"Labels":{"com.docker.compose.project":"unrelated"}}]'})()
        with patch.object(bench,'command',return_value=result), patch.object(bench,'compose') as compose:
            with self.assertRaisesRegex(RuntimeError,'ownership mismatch'):
                bench.init()
            compose.assert_not_called()

    def test_every_compose_command_has_independent_project_and_env(self):
        for size in bench.SIZES:
            args=bench.compose(size)
            self.assertEqual(args[args.index('-p')+1],'course-registration-bench')
            self.assertTrue(args[args.index('--env-file')+1].endswith('.bench-results/bench.env'))
            self.assertNotEqual(args[args.index('-f')+1],str(bench.ROOT/'compose.yaml'))

    def test_cgroup_v1_v2_normalized_units_and_missing_values(self):
        result=bench.parse_cgroup('FILE:cpu.stat\nusage_usec 1500000\nthrottled_usec 12000\nFILE:memory.current\n1048576\nFILE:memory.max\nmax\nFILE:memory.events\noom_kill 0\n')
        self.assertEqual(result['cpu.stat']['usage_usec'],1500000)
        self.assertEqual(result['memory.current'],1048576)
        self.assertIsNone(result['memory.max'])

    def test_late_arrivals_and_clock_jump_remain_visible(self):
        bench.OUT.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=bench.OUT) as directory:
            path=Path(directory)/'points.gz'
            with gzip.open(path,'wt') as output:
                for offset,jump in [(0,0),(100,0),(1100,2500)]:
                    at=dt.datetime.fromtimestamp(1700000000+(offset+jump)/1000,dt.timezone.utc).isoformat()
                    output.write(json.dumps({'type':'Point','metric':'iteration_start_ms','data':{'time':at,'value':offset}})+'\n')
                output.write(json.dumps({'type':'Point','metric':'response_finish_ms','data':{'value':1220}})+'\n')
            result=bench.point_summary(path,{'seconds':1})
            self.assertEqual(result['started_iterations'],3)
            self.assertEqual(result['arrivals_in_offered_window'],2)
            self.assertAlmostEqual(result['drain_seconds'],1.22)
            self.assertAlmostEqual(result['clock_discontinuity_ms'],2500,places=2)

if __name__=='__main__':
    unittest.main()
