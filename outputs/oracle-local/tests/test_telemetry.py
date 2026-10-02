import unittest
from telemetry import measurement,prompt_parts
class TelemetryTests(unittest.TestCase):
 def test_counts_partition_exact_prompt(self):
  prompt,parts=prompt_parts('指示',{'evidence':['價',12],'quantitative':{'p':98.8}})
  self.assertEqual(sum(parts.values()),len(prompt))
 def test_failure_has_end_and_error(self):
  entries=[]
  with self.assertRaises(ValueError):
   with measurement(lambda kind,e:entries.append(e),'models','test'):
    raise ValueError('failure')
  self.assertEqual(entries[0]['status'],'error')
  self.assertIn('ended_at',entries[0]);self.assertGreaterEqual(entries[0]['seconds'],0)
 def test_output_measured_after_success(self):
  entries=[]
  with measurement(lambda kind,e:entries.append(e),'models','test') as entry:entry['output_characters']=3
  self.assertEqual(entries[0]['output_characters'],3)
