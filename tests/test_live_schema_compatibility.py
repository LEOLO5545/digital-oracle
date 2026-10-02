"""Regressions derived from public API payloads observed 2026-09-30."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from digital_oracle.providers.cftc import CftcCotProvider
from digital_oracle.providers.kalshi import KalshiProvider

class LiveSchemaTests(unittest.TestCase):
    def test_cftc_current_field_names_preserve_real_positions(self):
        record={'prod_merc_positions_long':'242','prod_merc_positions_short':'0',
                'm_money_positions_spread':'17','other_rept_positions_long':'40980',
                'other_rept_positions_short':'64552','other_rept_positions_spread':'5153'}
        r=CftcCotProvider()._parse_reports([record])[0]
        self.assertEqual((r.prod_long,r.prod_short,r.mm_spread,r.other_long,r.other_short,r.other_spread),
                         (242,0,17,40980,64552,5153))
        self.assertEqual(r.prod_net,242)

    def test_kalshi_dollars_and_fixed_point_fields_are_not_lost(self):
        raw={'yes_bid_dollars':'0.4200','yes_ask_dollars':'0.4400',
             'no_bid_dollars':'0.5600','no_ask_dollars':'0.5800','last_price_dollars':'0.4300',
             'volume_fp':'123.50','volume_24h_fp':'42.25','open_interest_fp':'100.00',
             'liquidity_dollars':'56.75'}
        m=KalshiProvider()._parse_market(raw)
        self.assertEqual((m.yes_bid,m.yes_ask,m.no_bid,m.no_ask,m.last_price),(.42,.44,.56,.58,.43))
        self.assertAlmostEqual(m.yes_probability,.43)
        self.assertEqual((m.volume,m.volume_24h,m.open_interest,m.liquidity),(123.5,42.25,100,56.75))

    def test_kalshi_zero_dollars_are_not_replaced_by_legacy_price(self):
        m=KalshiProvider()._parse_market({'yes_bid_dollars':'0.0000','yes_bid':50,'yes_ask_dollars':'0.0100'})
        self.assertEqual(m.yes_bid,0)
        self.assertEqual(m.yes_probability,.005)

if __name__=='__main__':unittest.main()
