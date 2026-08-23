from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SwipeTabSourceTests(unittest.TestCase):
    def read_view(self, name: str) -> str:
        return (ROOT / "frontend" / "src" / "views" / name).read_text(
            encoding="utf-8"
        )

    def read_composable(self, name: str) -> str:
        return (ROOT / "frontend" / "src" / "composables" / name).read_text(
            encoding="utf-8"
        )

    def test_shared_horizontal_swipe_guard(self):
        source = self.read_composable("useHorizontalSwipe.ts")

        for token in (
            "threshold = 36",
            "directionRatio = 1.25",
            "onTouchStart",
            "onTouchMove",
            "onTouchEnd",
            "onTouchCancel",
            "onClickCapture",
            "preventDefault",
            "onBeforeUnmount",
            "activeTouchId",
            "gestureCancelled",
            "findTouch",
            "isClearlyVertical",
            "swipeDirection",
            "swipeDirection === null",
            "horizontalMoveCount",
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)
        self.assertIn("if (!tracking || gestureCancelled) return", source)
        self.assertIn("if (event.touches.length !== 1) {\n      cancelGesture()", source)
        self.assertIn("if (event.touches.length !== 0) {\n      resetGesture()", source)

    def test_navigation_and_filter_controls_are_excluded_from_page_swipes(self):
        composable = self.read_composable("useHorizontalSwipe.ts")

        for token in (
            "excludeSelector?: string",
            "isTouchExcluded",
            "closest(excludeSelector)",
            "querySelectorAll<HTMLElement>(excludeSelector)",
            "getBoundingClientRect",
        ):
            with self.subTest(token=token):
                self.assertIn(token, composable)

        excluded_selectors = {
            "Home.vue": (
                "excludeSelector: '.van-nav-bar, .van-tabbar, "
                ".van-search, .van-tabs__wrap'"
            ),
            "Orders.vue": (
                "excludeSelector: '.van-nav-bar, .van-tabbar, .van-tabs__wrap'"
            ),
        }
        for view_name, expected in excluded_selectors.items():
            with self.subTest(view=view_name):
                self.assertIn(expected, self.read_view(view_name))

    def test_home_uses_page_swipe_category_panels_with_isolated_state(self):
        source = self.read_view("Home.vue")

        self.assertIn("useHorizontalSwipe", source)
        self.assertIn("animated", source)
        self.assertIn("sticky", source)
        self.assertIn("swipe-surface", source)
        self.assertIn("min-height: calc(100svh - 50px)", source)
        self.assertIn("touch-action: pan-y", source)
        self.assertIn("switchCategory", source)
        for event in ("@touchstart", "@touchmove", "@touchend", "@touchcancel", "@click.capture"):
            with self.subTest(event=event):
                self.assertIn(event, source)
        self.assertNotIn("swipeable", source)
        self.assertIn('v-for="tab in categoryTabs"', source)
        self.assertIn("dishPages", source)
        self.assertIn("requestId", source)
        self.assertIn("const FAVORITES_TAB_ID = -1", source)
        self.assertIn("const ALL_TAB_ID = 0", source)
        self.assertIn("getFavoriteDishes({ search: keyword || undefined })", source)
        self.assertIn("<TransitionGroup", source)

    def test_home_favorites_tab_precedes_all_and_backend_categories(self):
        source = self.read_view("Home.vue")

        favorites = source.index("{ id: FAVORITES_TAB_ID, name: '收藏' }")
        all_dishes = source.index("{ id: ALL_TAB_ID, name: '全部' }")
        backend_categories = source.index("...categories.value")
        self.assertLess(favorites, all_dishes)
        self.assertLess(all_dishes, backend_categories)
        self.assertIn("const activeCategory = ref(initialCategory)", source)

    def test_home_dish_panel_height_follows_content(self):
        source = self.read_view("Home.vue")

        self.assertIn('class="dish-page"', source)
        self.assertNotIn("min-height: 220px", source)

    def test_orders_use_page_swipe_panels_for_every_status(self):
        source = self.read_view("Orders.vue")

        self.assertIn("useHorizontalSwipe", source)
        self.assertIn("animated", source)
        self.assertIn("swipe-surface", source)
        self.assertIn("min-height: calc(100svh - 50px)", source)
        self.assertIn("touch-action: pan-y", source)
        self.assertIn("switchStatus", source)
        for event in ("@touchstart", "@touchmove", "@touchend", "@touchcancel", "@click.capture"):
            with self.subTest(event=event):
                self.assertIn(event, source)
        self.assertNotIn("swipeable", source)
        self.assertIn('v-for="tab in ORDER_TABS"', source)
        self.assertIn("orderPages", source)
        for status in ("pending", "accepted", "cooking", "done", "cancelled"):
            with self.subTest(status=status):
                self.assertIn(f"name: '{status}'", source)


if __name__ == "__main__":
    unittest.main()
