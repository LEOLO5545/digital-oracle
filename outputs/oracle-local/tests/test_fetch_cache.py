import unittest
from fetch_cache import cache_key,usable
class CacheTests(unittest.TestCase):
 def test_different_question_labels_share_same_data_key(self):
  self.assertEqual(cache_key('yahoo',{'ticker':'SPY','label':'a','search':'one'}),cache_key('yahoo',{'ticker':'SPY','label':'b','search':'two'}))
  self.assertNotEqual(cache_key('yahoo',{'ticker':'SPY'}),cache_key('yahoo',{'ticker':'ITA'}))
 def test_expiry_and_failed_data(self):
  row={'status':'ok','checked_at':'2026-09-30T00:00:00+00:00'}
  self.assertTrue(usable(row,1800,'2026-09-30T00:29:59+00:00'))
  self.assertFalse(usable(row,1800,'2026-09-30T00:30:00+00:00'))
  self.assertFalse(usable({**row,'status':'error'},1800,'2026-09-30T00:01:00+00:00'))
 def test_provider_retries_once_and_cached_result_retains_timestamp(self):
  import tempfile,json
  from pathlib import Path
  from unittest.mock import patch
  from types import SimpleNamespace
  import server
  with tempfile.TemporaryDirectory() as folder:
   response={'id':'yahoo','status':'ok','checked_at':server.now(),'data':{'price':12}}
   failed=SimpleNamespace(returncode=1,stdout='');ok=SimpleNamespace(returncode=0,stdout=json.dumps(response))
   with patch.object(server,'STATE',Path(folder)),patch.object(server,'run_tracked',side_effect=[failed,ok]) as fetch:
    first=server.get_source('yahoo',{'ticker':'SPY'});second=server.get_source('yahoo',{'ticker':'SPY','label':'different'})
   self.assertEqual(fetch.call_count,2);self.assertEqual(len(first['request_attempts']),2)
   self.assertTrue(second['cache_hit']);self.assertEqual(second['checked_at'],response['checked_at'])
