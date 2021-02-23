import electrum.mpp_split as mpp_split  # side effect for PART_PENALTY
from electrum.lnutil import NoPathFound

from . import ElectrumTestCase

PART_PENALTY = mpp_split.PART_PENALTY


class TestMppSplit(ElectrumTestCase):
    def setUp(self):
        super().setUp()
        # undo side effect
        mpp_split.PART_PENALTY = PART_PENALTY
        self.channels_with_funds = {
            0: 1_000_000_000,
            1: 500_000_000,
            2: 302_000_000,
            3: 101_000_000,
        }

    def test_suggest_splits(self):
        with self.subTest(msg="do a payment with the maximal amount spendable over a single channel"):
            splits = mpp_split.suggest_splits(1_000_000_000, self.channels_with_funds, exclude_single_parts=True)
            self.assertEqual({0: 500_000_000, 1: 500_000_000, 2: 0, 3: 0}, splits[0][0])

        with self.subTest(msg="do a payment with a larger amount than what is supported by a single channel"):
            splits = mpp_split.suggest_splits(1_100_000_000, self.channels_with_funds, exclude_single_parts=True)
            self.assertEqual(2, mpp_split.number_nonzero_parts(splits[0][0]))

        with self.subTest(msg="do a payment with the maximal amount spendable over all channels"):
            splits = mpp_split.suggest_splits(sum(self.channels_with_funds.values()), self.channels_with_funds, exclude_single_parts=True)
            self.assertEqual({0: 1_000_000_000, 1: 500_000_000, 2: 302_000_000, 3: 101_000_000}, splits[0][0])

        with self.subTest(msg="do a payment with the amount supported by all channels"):
            splits = mpp_split.suggest_splits(101_000_000, self.channels_with_funds, exclude_single_parts=False)
            for s in splits[:4]:
                self.assertEqual(1, mpp_split.number_nonzero_parts(s[0]))

    def test_payment_below_min_part_size(self):
        amount = mpp_split.MIN_PART_MSAT // 2
        splits = mpp_split.suggest_splits(amount, self.channels_with_funds, exclude_single_parts=False)
        # we only get four configurations that end up spending the full amount
        # in a single channel
        self.assertEqual(4, len(splits))

    def test_suggest_part_penalty(self):
        """Test is mainly for documentation purposes.
        Decreasing the part penalty from 1.0 towards 0.0 leads to an increase
        in the number of parts a payment is split. A configuration which has
        about equally distributed amounts will result."""
        with self.subTest(msg="split payments with intermediate part penalty"):
            mpp_split.PART_PENALTY = 1.0
            splits = mpp_split.suggest_splits(1_100_000_000, self.channels_with_funds)
            self.assertEqual(2, mpp_split.number_nonzero_parts(splits[0][0]))

        with self.subTest(msg="split payments with intermediate part penalty"):
            mpp_split.PART_PENALTY = 0.3
            splits = mpp_split.suggest_splits(1_100_000_000, self.channels_with_funds)
            self.assertEqual(3, mpp_split.number_nonzero_parts(splits[0][0]))

        with self.subTest(msg="split payments with no part penalty"):
            mpp_split.PART_PENALTY = 0.0
            splits = mpp_split.suggest_splits(1_100_000_000, self.channels_with_funds)
            self.assertEqual(4, mpp_split.number_nonzero_parts(splits[0][0]))

    def test_suggest_splits_single_channel(self):
        channels_with_funds = {
            0: 1_000_000_000,
        }

        with self.subTest(msg="do a payment with the maximal amount spendable on a single channel"):
            splits = mpp_split.suggest_splits(1_000_000_000, channels_with_funds, exclude_single_parts=False)
            self.assertEqual({0: 1_000_000_000}, splits[0][0])
        with self.subTest(msg="test sending an amount greater than what we have available"):
            self.assertRaises(NoPathFound, mpp_split.suggest_splits, *(1_100_000_000, channels_with_funds))
