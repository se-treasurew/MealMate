import unittest
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class FavoriteFrontendSourceTests(unittest.TestCase):
    def test_dish_api_exposes_favorite_state_and_idempotent_calls(self):
        source = read("frontend/src/api/dish.ts")
        self.assertIn("is_favorite: boolean", source)
        self.assertIn("favoriteDish", source)
        self.assertIn("unfavoriteDish", source)
        self.assertIn("`/api/dishes/${id}/favorite`", source)
        self.assertIn("apiClient.put", source)
        self.assertIn("apiClient.delete", source)
        self.assertIn("getFavoriteDishes", source)
        self.assertIn("'/api/dishes/favorites'", source)
        self.assertIn("getFavoriteDishes = (params?: { search?: string })", source)
        self.assertIn("apiClient.get<Dish[]>('/api/dishes/favorites', { params })", source)

    def test_home_integrates_favorites_as_first_shared_dish_tab(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("const FAVORITES_TAB_ID = -1", source)
        self.assertIn("const ALL_TAB_ID = 0", source)
        self.assertIn("{ id: FAVORITES_TAB_ID, name: '收藏' }", source)
        self.assertIn("{ id: ALL_TAB_ID, name: '全部' }", source)
        self.assertLess(source.index("{ id: FAVORITES_TAB_ID"), source.index("{ id: ALL_TAB_ID"))
        self.assertLess(source.index("{ id: ALL_TAB_ID"), source.index("...categories.value"))
        self.assertIn("getFavoriteDishes", source)
        self.assertIn("<TransitionGroup", source)
        self.assertIn("<DishCard", source)
        self.assertNotIn("goFavorites", source)
        self.assertNotIn("favorites-entry", source)

    def test_home_has_guest_favorites_prompt_without_requesting_favorites(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("登录后查看收藏", source)
        self.assertIn('@click="goLogin"', source)
        self.assertRegex(
            source,
            re.compile(
                r"if \(categoryId === FAVORITES_TAB_ID && userStore\.isGuest\).*?return",
                re.DOTALL,
            ),
        )
        guest_guard = source.index(
            "if (categoryId === FAVORITES_TAB_ID && userStore.isGuest)"
        )
        favorite_request = source.index("await getFavoriteDishes", guest_guard)
        self.assertLess(guest_guard, favorite_request)

    def test_home_has_guarded_optimistic_favorite_controls(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("toggleFavorite", source)
        self.assertIn("userStore.isGuest", source)
        self.assertNotIn("sortDishesByFavorite", source)
        self.assertIn("favoriteUpdatingIds", source)
        self.assertGreaterEqual(
            source.count("updateCachedFavorite(dish.id, target)"),
            2,
            "收藏接口成功后必须重施目标状态，避免并发刷新覆盖乐观更新",
        )
        self.assertIn("removeDishFromFavoriteCache(dish.id)", source)
        self.assertIn("invalidateFavoriteCache()", source)

    def test_home_favorite_removal_is_optimistic_and_race_safe(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("removedIndex", source)
        self.assertIn("resultVersion", source)
        self.assertIn("operationResultVersion", source)
        self.assertIn("operationKeyword", source)
        self.assertIn("favoritePage.dishes.splice(removedIndex, 0, removedDish)", source)
        self.assertGreaterEqual(
            source.count("removeDishFromFavoriteCache(dish.id)"),
            2,
            "取消收藏应先乐观移除，并在成功后再次移除以抵御并发刷新",
        )

    def test_failed_unfavorite_reloads_when_original_result_cannot_be_restored(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("const canRestoreRemovedDish =", source)
        catch_start = source.index("} catch (error: any) {")
        fallback_start = source.index("if (!target) {", catch_start)
        fallback_end = source.index("showToast(error.response", fallback_start)
        fallback_body = source[fallback_start:fallback_end]
        self.assertIn("if (canRestoreRemovedDish && removedDish)", fallback_body)
        self.assertIn("favoritePage.loadedKeyword = null", fallback_body)
        self.assertIn("activeCategory.value === FAVORITES_TAB_ID", fallback_body)
        self.assertIn("void loadDishes(FAVORITES_TAB_ID, true)", fallback_body)

    def test_home_applies_favorite_mutation_overlay_to_late_list_responses(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("favoriteOverrides", source)
        self.assertIn("applyFavoriteOverrides", source)
        self.assertIn("favoriteOverrides.value.set(dish.id, target)", source)
        self.assertIn("favoriteOverrides.value.set(dish.id, previous)", source)
        self.assertIn("applyFavoriteOverrides(data, categoryId)", source)

    def test_transition_group_stays_mounted_when_last_favorite_is_removed(self):
        source = read("frontend/src/views/Home.vue")
        transition_start = source.index("<TransitionGroup")
        transition_end = source.index(">", transition_start)
        self.assertNotIn("v-if", source[transition_start:transition_end])
        self.assertIn('v-if="dishPages[tab.id].dishes.length === 0"', source)

    def test_home_favorites_search_uses_page_request_state(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("loadedKeyword", source)
        self.assertIn("requestId", source)
        self.assertIn("getFavoriteDishes({ search: keyword || undefined })", source)

    def test_shared_dish_card_exposes_consistent_actions(self):
        source = read("frontend/src/components/DishCard.vue")
        self.assertIn("dish: Dish", source)
        self.assertIn("favoriteUpdating", source)
        self.assertIn("emit('view'", source)
        self.assertIn("emit('toggleFavorite'", source)
        self.assertIn("emit('addToCart'", source)
        self.assertIn("dish.is_favorite", source)
        self.assertIn("@click.stop", source)

    def test_favorites_route_redirects_to_home_tab_for_guests(self):
        router = read("frontend/src/router/index.ts")
        app = read("frontend/src/App.vue")
        route_match = re.search(
            r"\{\s*path: '/favorites',(?P<body>.*?)\n\s*\},", router, re.DOTALL
        )
        self.assertIsNotNone(route_match)
        route_body = route_match.group("body")
        self.assertIn("path: '/favorites'", router)
        self.assertIn("redirect: { path: '/', query: { tab: 'favorites' } }", route_body)
        self.assertNotIn("component:", route_body)
        self.assertNotIn("requiresAuth", route_body)
        self.assertNotIn("'Favorites'", app)

    def test_legacy_favorites_view_is_removed(self):
        self.assertFalse((ROOT / "frontend/src/views/Favorites.vue").exists())

    def test_home_only_honors_exact_favorites_query_then_cleans_it(self):
        source = read("frontend/src/views/Home.vue")
        self.assertIn("route.query.tab === 'favorites'", source)
        self.assertIn("router.replace('/')", source)

    def test_detail_has_favorite_control_and_login_guard(self):
        source = read("frontend/src/views/DishDetail.vue")
        self.assertIn("toggleFavorite", source)
        self.assertIn("dish.is_favorite", source)
        self.assertIn("userStore.isGuest", source)
        self.assertIn("favoriteUpdating", source)

    def test_service_worker_does_not_cache_personalized_dish_responses(self):
        source = read("frontend/src/sw.ts")
        self.assertIn("url.pathname === '/api/dishes/favorites'", source)
        self.assertIn("!request.headers.has('Authorization')", source)
        self.assertIn("cacheName: 'api-menu-cache-v2'", source)


class PermanentOrderDeleteFrontendSourceTests(unittest.TestCase):
    def test_order_api_keeps_cancel_and_adds_permanent_delete(self):
        source = read("frontend/src/api/order.ts")
        self.assertIn("cancelOrder", source)
        self.assertIn("permanentlyDeleteOrder", source)
        self.assertIn("`/api/orders/${id}/permanent`", source)

    def test_orders_list_guards_cancel_and_permanent_delete(self):
        source = read("frontend/src/views/Orders.vue")
        self.assertIn("canCancel(order)", source)
        self.assertIn("canPermanentlyDelete(order)", source)
        self.assertIn("userStore.isAdmin", source)
        self.assertIn("permanentlyDeleteOrder", source)
        self.assertIn("订单明细和关联评价将无法恢复", source)

    def test_order_detail_has_admin_only_permanent_delete(self):
        source = read("frontend/src/views/OrderDetail.vue")
        self.assertIn("canPermanentlyDelete", source)
        self.assertIn("userStore.isAdmin", source)
        self.assertIn("permanentlyDeleteOrder", source)
        self.assertIn("订单明细和关联评价将无法恢复", source)

    def test_order_items_include_current_image_and_availability(self):
        api_source = read("frontend/src/api/order.ts")
        detail_source = read("frontend/src/views/OrderDetail.vue")
        self.assertIn("dish_image_path: string | null", api_source)
        self.assertIn("dish_available: boolean", api_source)
        self.assertIn("imageUrl(item.dish_image_path)", detail_source)
        self.assertIn("item.dish_available", detail_source)
        self.assertIn("goDishDetail(item)", detail_source)
        self.assertIn("from_order: String(order.value.id)", detail_source)

    def test_dish_detail_returns_to_origin_order_safely(self):
        source = read("frontend/src/views/DishDetail.vue")
        self.assertIn("@click-left=\"goBack\"", source)
        self.assertIn("returnOrderId", source)
        self.assertIn("window.history.state?.back", source)
        self.assertIn("router.replace(`/orders/${returnOrderId.value}`)", source)


if __name__ == "__main__":
    unittest.main()
