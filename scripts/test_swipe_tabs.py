from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SwipeTabSourceTests(unittest.TestCase):
    def read_view(self, name: str) -> str:
        return (ROOT / "frontend" / "src" / "views" / name).read_text(
            encoding="utf-8"
        )

    def test_home_uses_swipeable_category_panels_with_isolated_state(self):
        source = self.read_view("Home.vue")

        self.assertIn("swipeable", source)
        self.assertIn("animated", source)
        self.assertIn("sticky", source)
        self.assertIn('v-for="tab in categoryTabs"', source)
        self.assertIn("dishPages", source)
        self.assertIn("requestId", source)

    def test_home_dish_panel_height_follows_content(self):
        source = self.read_view("Home.vue")

        self.assertIn('class="dish-page"', source)
        self.assertNotIn("min-height: 220px", source)

    def test_orders_use_swipeable_panels_for_every_status(self):
        source = self.read_view("Orders.vue")

        self.assertIn("swipeable", source)
        self.assertIn("animated", source)
        self.assertIn('v-for="tab in ORDER_TABS"', source)
        self.assertIn("orderPages", source)
        for status in ("pending", "accepted", "cooking", "done", "cancelled"):
            with self.subTest(status=status):
                self.assertIn(f"name: '{status}'", source)


if __name__ == "__main__":
    unittest.main()
