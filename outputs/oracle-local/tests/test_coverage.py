import unittest
from coverage import signal_counts
class CountTests(unittest.TestCase):
 def test_supplements_and_retries_count_once(self):
  p={'signals':[{'id':str(i)} for i in range(36)]}
  rows=[{'id':str(i),'status':'ok'} for i in range(36)]
  rows.insert(0,{'id':'0','status':'error'})
  self.assertEqual(signal_counts(p,rows),{'planned':36,'received':36,'successful':36,'failed':0})
