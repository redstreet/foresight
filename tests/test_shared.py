import unittest

from common.shared import foresight_config_section, get_foresight_config


class Custom:
    def __init__(self, custom_type, values):
        self.type = custom_type
        self.values = values


class SharedTest(unittest.TestCase):
    def test_get_foresight_config_reads_foresight_custom_directive(self):
        entries = [
            Custom(
                "foresight",
                [
                    "foresight",
                    "{'investments': {'breakdown': {'brokerages': ['Fidelity', 'Vanguard']}}}",
                ],
            )
        ]
        self.assertEqual(
            get_foresight_config(entries, None),
            {
                "investments": {
                    "breakdown": {
                        "brokerages": ["Fidelity", "Vanguard"],
                    },
                },
            },
        )

    def test_foresight_config_section_merges_nested_config_over_defaults(self):
        config = {
            "investments": {
                "cash_drag": {
                    "accounts_pattern": "^Assets:Investments",
                },
            },
        }

        self.assertEqual(
            foresight_config_section(
                config,
                "investments.cash_drag",
                {
                    "accounts_pattern": "^Assets",
                    "min_threshold": 0,
                },
            ),
            {
                "accounts_pattern": "^Assets:Investments",
                "min_threshold": 0,
            },
        )

    def test_foresight_config_section_rejects_non_dict_section(self):
        with self.assertRaises(ValueError):
            foresight_config_section(
                {"investments": {"cash_drag": []}},
                "investments.cash_drag",
                {},
            )


if __name__ == "__main__":
    unittest.main()
