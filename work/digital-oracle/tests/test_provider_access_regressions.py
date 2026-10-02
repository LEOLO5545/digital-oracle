from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from digital_oracle.providers.coingecko import CoinGeckoProvider
from digital_oracle.providers.edgar import EdgarProvider, EdgarSearchQuery
from digital_oracle.http import UrllibJsonClient

class AccessRegressionTests(unittest.TestCase):
    def test_demo_key_is_sent_as_header_not_url(self):
        requests = []
        def capture(client, request):
            from io import BytesIO
            requests.append(request)
            return BytesIO(b'{"bitcoin":{"usd":123}}')
        with patch.dict('os.environ', {'COINGECKO_DEMO_API_KEY': 'test-demo-key'}):
            with patch.object(UrllibJsonClient, '_open', capture):
                rows = CoinGeckoProvider().get_prices()
        self.assertEqual(rows[0].price_usd, 123)
        self.assertEqual(dict(requests[0].header_items()).get('X-cg-demo-api-key'), 'test-demo-key')
        self.assertNotIn('test-demo-key', requests[0].full_url)

    def test_sec_live_search_schema_preserves_entity_form_and_file_number(self):
        sample = json.loads((Path(__file__).parent/'fixtures/edgar_live_search_source.json').read_text())
        class Client:
            def get_json(self, url, *, params=None):
                return {'hits': {'hits': [{'_source': sample}]}}
        hit = EdgarProvider(Client()).search_filings(EdgarSearchQuery('artificial intelligence'))[0]
        self.assertEqual(hit.entity_name, 'Artificial Intelligence Technology Solutions Inc.  (AITX)  (CIK 0001498148)')
        self.assertEqual(hit.form_type, '10-K')
        self.assertEqual(hit.file_number, '000-55079')
