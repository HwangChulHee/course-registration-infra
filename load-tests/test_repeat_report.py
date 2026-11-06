import importlib.util
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('repeat_report',Path(__file__).resolve().parents[1]/'scripts/report-repeat.py')
report=importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)

class RepeatedStatisticsTests(unittest.TestCase):
    def test_sample_statistics(self):
        d=report.describe([1,3,None])
        self.assertEqual(d['n'],2)
        self.assertEqual(d['mean'],2)
        self.assertEqual(d['median'],2)
        self.assertAlmostEqual(d['sample_stddev'],2**0.5)

    def test_single_trial_does_not_invent_deviation(self):
        self.assertIsNone(report.describe([100])['sample_stddev'])
        self.assertEqual(report.describe([])['n'],0)
        self.assertIsNone(report.describe([None])['mean'])

    def test_full_duplicate_are_not_server_failures_and_inflight_is_separate(self):
        r=report.rates({'responses_finished':1000,'requests_started':1200,'server_5xx':0,'network_errors':0,'full':997,'duplicate':0})
        self.assertEqual(r['server_5xx_rate'],0)
        self.assertEqual(r['business_conflict_rate'],0.997)
        self.assertEqual(r['unfinished_requests'],200)
        self.assertIsNone(report.rates({'responses_finished':0,'requests_started':10,'server_5xx':0,'network_errors':0,'full':0,'duplicate':0})['server_5xx_rate'])

class OriginalCohortProtectionTests(unittest.TestCase):
    def test_original_export_cannot_mix_new_trials_into_published_baseline(self):
        old_spec=importlib.util.spec_from_file_location('original_report',Path(__file__).resolve().parents[1]/'scripts/report-bench.py')
        original=importlib.util.module_from_spec(old_spec)
        old_spec.loader.exec_module(original)
        root=Path(__file__).resolve().parents[1]/'.bench-results'
        with tempfile.TemporaryDirectory(dir=root) as directory:
            study=Path(directory)/'repeat-study'
            study.mkdir()
            (study/'manifest.json').write_text('{}')
            with patch.object(original,'OUT',Path(directory)):
                with self.assertRaisesRegex(SystemExit,'cohort is frozen'):
                    original.main()

if __name__=='__main__': unittest.main()
