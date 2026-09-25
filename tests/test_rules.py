import random
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "anki_farm"))

from game import rules, settings  # noqa: E402
from game.catalog import MAX_TIER, PACKET_SIZE, PACKETS_PER_DAY, SPECIES_BY_ID  # noqa: E402
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


class EarnsSeedTests(unittest.TestCase):
    """Only answers that complete a card earn a seed."""

    def earns(self, ease=3, review_type=1, ivl=5, time_ms=4000):
        return rules.earns_seed(
            ease=ease, review_type=review_type, ivl=ivl, time_ms=time_ms, min_ms=1500
        )

    def test_passed_review(self):
        self.assertTrue(self.earns())

    def test_graduating_new_card(self):
        self.assertTrue(self.earns(review_type=0, ivl=1))

    def test_learning_step_earns_nothing(self):
        self.assertFalse(self.earns(review_type=0, ivl=-600))  # next step in 10 min

    def test_lapse_into_relearning_earns_nothing(self):
        self.assertFalse(self.earns(ease=1, review_type=1, ivl=-600))

    def test_relearned_card_back_in_review(self):
        self.assertTrue(self.earns(review_type=2, ivl=1))

    def test_every_button_is_equal_when_it_completes(self):
        for ease in (1, 2, 3, 4):
            self.assertTrue(self.earns(ease=ease, ivl=3))

    def test_too_fast_or_manual(self):
        self.assertFalse(self.earns(time_ms=800))
        self.assertFalse(self.earns(ease=0, review_type=4))  # manual reschedule
        self.assertFalse(self.earns(review_type=3, ivl=0))  # filtered-deck preview


class PacketTests(unittest.TestCase):
    def test_packet_once_per_deck_per_day(self):
        s = FarmState()
        seeds = rules.claim_packet(s, day=100, deck_id=1, revlog_id=9, rng=random.Random(3))
        self.assertEqual(len(seeds), PACKET_SIZE)
        self.assertEqual(s.bag_total(), PACKET_SIZE)
        self.assertIsNone(rules.claim_packet(s, day=100, deck_id=1))
        self.assertIsNotNone(rules.claim_packet(s, day=101, deck_id=1))

    def test_packet_has_a_rare_or_better(self):
        rng = random.Random(7)
        for day in range(200):
            seeds = rules.claim_packet(FarmState(), day=day, deck_id=1, rng=rng)
            self.assertIn(SPECIES_BY_ID[seeds[-1]].rarity, ("rare", "epic", "legendary"))

    def test_daily_packet_limit(self):
        s = FarmState()
        for deck in range(PACKETS_PER_DAY):
            self.assertIsNotNone(rules.claim_packet(s, day=5, deck_id=deck))
        self.assertIsNone(rules.claim_packet(s, day=5, deck_id=99))

    def test_undo_takes_packet_back_and_reopens_it(self):
        s = FarmState()
        rules.claim_packet(s, day=5, deck_id=1, revlog_id=42)
        for reward in [r for r in s.recent_rewards if r["rid"] == 42]:
            rules.revoke_reward(s, reward)
        self.assertEqual(s.bag, {})
        self.assertEqual(s.stats.get("packets"), 0)
        self.assertIsNotNone(rules.claim_packet(s, day=5, deck_id=1))

    def test_packet_state_survives_save(self):
        s = FarmState()
        rules.claim_packet(s, day=5, deck_id=1)
        again = FarmState.from_dict(s.to_dict())
        self.assertIsNone(rules.claim_packet(again, day=5, deck_id=1))


class CatchUpTests(unittest.TestCase):
    """Reviews done on a phone arrive later through sync."""

    def test_phone_reviews_earn_seeds_once(self):
        s = FarmState(start_rid=0)
        phone = [(100 + i, 10, False) for i in range(5)]
        self.assertEqual(len(rules.catch_up(s, phone, today=10)), 5)
        self.assertEqual(rules.catch_up(s, phone, today=10), [])
        self.assertEqual(s.bag_total(), 5)

    def test_desktop_reviews_are_not_paid_twice(self):
        s = FarmState(start_rid=0)
        rules.grant_seed(s, "corn", revlog_id=500, review_day=10)  # live, desktop
        reviews = [(500, 10, False), (90, 10, False), (91, 10, False)]  # + 2 from phone
        self.assertEqual(len(rules.catch_up(s, reviews, today=10)), 2)
        self.assertEqual(s.bag_total(), 3)

    def test_late_sync_from_earlier_day(self):
        s = FarmState(start_rid=0)
        rules.grant_seed(s, "corn", revlog_id=900, review_day=11)
        # phone reviews from yesterday only sync today
        reviews = [(800, 10, False), (801, 10, True), (900, 11, False)]
        self.assertEqual(len(rules.catch_up(s, reviews, today=11)), 2)

    def test_reviews_before_install_ignored(self):
        s = FarmState()
        rules.ensure_started(s, now_rid=1000)
        rules.ensure_started(s, now_rid=5000)  # only the first call counts
        reviews = [(999, 10, False), (1000, 10, False)]
        self.assertEqual(len(rules.catch_up(s, reviews, today=10)), 1)

    def test_undo_of_live_review_frees_the_count(self):
        s = FarmState(start_rid=0)
        rules.grant_seed(s, "corn", revlog_id=5, review_day=10)
        rules.revoke_reward(s, s.recent_rewards[0])
        self.assertEqual(s.review_days.get(10), 0)
        self.assertEqual(rules.catch_up(s, [], today=10), [])

    def test_old_days_pruned(self):
        s = FarmState(start_rid=0, review_days={1: 4, 50: 2})
        rules.catch_up(s, [], today=50)
        self.assertEqual(s.review_days, {50: 2})

    def test_round_trip_keeps_counts(self):
        s = FarmState(start_rid=7, review_days={10: 3})
        again = FarmState.from_dict(s.to_dict())
        self.assertEqual((again.start_rid, again.review_days), (7, {10: 3}))


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


class SettingsTests(unittest.TestCase):
    def test_defaults_filled_in(self):
        current = settings.current({"sound": False})
        self.assertFalse(current["sound"])
        self.assertEqual(current["min_answer_seconds"], 1.5)

    def test_bad_input_rejected_or_clamped(self):
        with self.assertRaises(ValueError):
            settings.clean("seen_howto", True)  # not user-editable from the panel
        with self.assertRaises(ValueError):
            settings.clean("sound", "yes")
        with self.assertRaises(ValueError):
            settings.clean("min_answer_seconds", "abc")
        self.assertEqual(settings.clean("min_answer_seconds", 99), 10.0)
        self.assertEqual(settings.clean("min_answer_seconds", -3), 0.0)
        self.assertEqual(settings.clean("min_answer_seconds", "2.25"), 2.2)


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
