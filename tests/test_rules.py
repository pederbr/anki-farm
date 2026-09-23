import random
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "anki_farm"))

from game import rules  # noqa: E402
from game.catalog import MAX_TIER, SPECIES_BY_ID  # noqa: E402
from game.state import FarmState, Plant  # noqa: E402


class RewardTests(unittest.TestCase):
    def test_seed_goes_to_bag_by_default(self):
        s = FarmState()
        tile = rules.grant_seed(s, "wheat", revlog_id=1)
        self.assertIsNone(tile)
        self.assertEqual(s.bag, {"wheat": 1})
        self.assertEqual(s.almanac, {"wheat": 1})

    def test_auto_plant_uses_empty_tile_then_bag(self):
        s = FarmState(width=1, height=1)
        self.assertEqual(rules.grant_seed(s, "wheat", auto_plant=True), "0,0")
        self.assertIsNone(rules.grant_seed(s, "wheat", auto_plant=True))
        self.assertEqual(s.bag, {"wheat": 1})

    def test_revoke_from_bag_and_tile(self):
        s = FarmState()
        rules.grant_seed(s, "corn", revlog_id=1)
        rules.grant_seed(s, "corn", revlog_id=2, auto_plant=True, rng=random.Random(0))
        r1, r2 = s.recent_rewards
        self.assertTrue(rules.revoke_reward(s, r2))
        self.assertEqual(s.tiles, {})
        self.assertTrue(rules.revoke_reward(s, r1))
        self.assertEqual(s.bag, {})
        self.assertEqual(s.recent_rewards, [])

    def test_revoke_after_merge_is_best_effort(self):
        s = FarmState()
        rules.grant_seed(s, "corn", revlog_id=1)
        rules.grant_seed(s, "corn", revlog_id=2)
        rules.plant_from_bag(s, "corn", "0,0")
        rules.plant_from_bag(s, "corn", "0,0")  # merges into a sprout
        self.assertFalse(rules.revoke_reward(s, s.recent_rewards[0]))
        self.assertEqual(s.tiles["0,0"], Plant("corn", 2))

    def test_rarity_distribution_is_roughly_right(self):
        rng = random.Random(42)
        counts = Counter(
            SPECIES_BY_ID[rules.roll_species(rng)].rarity for _ in range(20000)
        )
        self.assertAlmostEqual(counts["common"] / 20000, 0.60, delta=0.02)
        self.assertGreater(counts["legendary"], 0)

    def test_mature_boost_shifts_rarity(self):
        rng = random.Random(1)
        normal = sum(rules.roll_rarity(rng) != "common" for _ in range(20000))
        boosted = sum(rules.roll_rarity(rng, mature=True) != "common" for _ in range(20000))
        self.assertGreater(boosted, normal)


class BoardTests(unittest.TestCase):
    def setUp(self):
        self.s = FarmState()

    def test_merge_two_identical(self):
        self.s.tiles = {"0,0": Plant("tomato", 3), "1,0": Plant("tomato", 3)}
        result = rules.move(self.s, "0,0", "1,0")
        self.assertEqual(result.kind, "merge")
        self.assertTrue(result.new_discovery)
        self.assertEqual(self.s.tiles, {"1,0": Plant("tomato", 4)})
        self.assertEqual(self.s.almanac["tomato"], 4)

    def test_different_plants_swap(self):
        self.s.tiles = {"0,0": Plant("tomato", 3), "1,0": Plant("tomato", 2)}
        self.assertEqual(rules.move(self.s, "0,0", "1,0").kind, "swap")
        self.assertEqual(self.s.tiles["0,0"], Plant("tomato", 2))

    def test_golden_crops_do_not_merge(self):
        self.s.tiles = {"0,0": Plant("corn", MAX_TIER), "1,0": Plant("corn", MAX_TIER)}
        self.assertEqual(rules.move(self.s, "0,0", "1,0").kind, "swap")

    def test_move_to_empty(self):
        self.s.tiles = {"0,0": Plant("corn", 1)}
        self.assertEqual(rules.move(self.s, "0,0", "4,4").kind, "move")
        self.assertEqual(list(self.s.tiles), ["4,4"])

    def test_out_of_bounds_rejected(self):
        self.s.tiles = {"0,0": Plant("corn", 1)}
        for bad in ("5,0", "-1,0", "nonsense", ""):
            with self.assertRaises(rules.GameError):
                rules.move(self.s, "0,0", bad)

    def test_plant_needs_seed_in_bag(self):
        with self.assertRaises(rules.GameError):
            rules.plant_from_bag(self.s, "corn", "0,0")

    def test_plant_all_fills_board(self):
        self.s = FarmState(width=2, height=2)
        self.s.bag = {"corn": 3, "coffee": 2}
        self.assertEqual(rules.plant_all(self.s, random.Random(0)), 4)
        self.assertEqual(self.s.bag, {"corn": 1})  # rarest planted first

    def test_return_seed_to_bag(self):
        self.s.tiles = {"0,0": Plant("corn", 1), "1,0": Plant("corn", 2)}
        rules.return_to_bag(self.s, "0,0")
        self.assertEqual(self.s.bag, {"corn": 1})
        with self.assertRaises(rules.GameError):
            rules.return_to_bag(self.s, "1,0")

    def test_full_chain_to_golden_takes_64_seeds(self):
        s = FarmState(width=8, height=8)
        s.bag = {"wheat": 64}
        rules.plant_all(s)
        while len(s.tiles) > 1:
            by_tier = {}
            for key, p in sorted(s.tiles.items()):
                if p.tier in by_tier:
                    rules.move(s, key, by_tier.pop(p.tier))
                    break
                by_tier[p.tier] = key
        self.assertEqual(list(s.tiles.values()), [Plant("wheat", MAX_TIER)])
        self.assertEqual(s.stats["golden_crops"], 1)


class SerializationTests(unittest.TestCase):
    def test_round_trip(self):
        s = FarmState()
        rules.grant_seed(s, "rose", revlog_id=5)
        s.tiles["2,2"] = Plant("melon", 6)
        again = FarmState.from_dict(s.to_dict())
        self.assertEqual(again, s)

    def test_empty_and_garbage(self):
        self.assertEqual(FarmState.from_dict(None), FarmState())
        s = FarmState.from_dict({"tiles": {"0,0": ["dragonfruit", 1]}, "bag": {"x": 3}})
        self.assertEqual(s.tiles, {})
        self.assertEqual(s.bag, {})


if __name__ == "__main__":
    unittest.main()
