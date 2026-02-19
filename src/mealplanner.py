"""MyMealPlanner integration — extracts meal plan data into HA entities."""

import logging
from datetime import date, timedelta
from typing import Any

from .ha_client import HomeAssistantClient

logger = logging.getLogger(__name__)

# Only keep plans within this window of today to prevent unbounded memory growth
_CACHE_WINDOW_DAYS = 30


class MealPlannerHandler:
    """Handles MyMealPlanner events (d-tag prefix 'mmp:') and updates HA entities."""

    def __init__(self, ha_client: HomeAssistantClient, entity_prefix: str = "nostr"):
        self._ha = ha_client
        self._prefix = entity_prefix
        # Cache all meal plans so we can find today's
        self._plans: dict[str, dict[str, Any]] = {}  # date_str -> plan data
        self._last_today: str = ""  # Track date changes

    async def handle_plan_event(self, data: dict[str, Any], d_tag: str) -> None:
        """Process a meal plan event from MyMealPlanner."""
        # Check for deletion marker
        if data.get("_deleted"):
            plan_date = self._find_date_by_dtag(d_tag)
            if plan_date and plan_date in self._plans:
                del self._plans[plan_date]
                logger.info("Removed deleted meal plan for %s", plan_date)
                await self._update_todays_meal()
            return

        plan_date = data.get("date")
        if not plan_date:
            logger.warning("Meal plan event missing 'date' field: %s", d_tag)
            return

        # Only cache dates within a reasonable window to prevent memory exhaustion
        if not self._is_date_in_window(plan_date):
            logger.debug("Ignoring plan outside cache window: %s", plan_date)
            return

        # Log the full structure on first plan to help debug
        meal_data = data.get("meal_data", {})
        logger.info(
            "Cached meal plan for %s: title=%s, keys=%s",
            plan_date,
            meal_data.get("title", "<no title>"),
            list(meal_data.keys()) if isinstance(meal_data, dict) else type(meal_data).__name__,
        )

        self._plans[plan_date] = data
        self._prune_old_plans()
        await self._update_todays_meal()

    async def refresh_today(self) -> bool:
        """Re-evaluate today's meal. Called periodically by the main loop.

        Returns True if the date changed (caller should re-fetch from relays).
        """
        today_str = date.today().strftime("%Y-%m-%d")
        if today_str != self._last_today:
            logger.info("Date changed to %s — refreshing today's meal", today_str)
            await self._update_todays_meal()
            return True
        return False

    async def _update_todays_meal(self) -> None:
        """Update the HA sensor with today's meal plan."""
        today_str = date.today().strftime("%Y-%m-%d")
        self._last_today = today_str
        plan = self._plans.get(today_str)

        entity_id = f"sensor.{self._prefix}_todays_meal"

        if plan:
            meal_data = plan.get("meal_data", {})
            title = meal_data.get("title", "Unknown Meal")
            rating = meal_data.get("rating")
            from_freezer = plan.get("fromFreezer", False)
            tags = meal_data.get("tags", [])
            description = meal_data.get("description", "")
            image = meal_data.get("image", "")

            attributes = {
                "friendly_name": "Today's Meal",
                "icon": "mdi:food",
                "source": "nostr_mealplanner",
                "date": today_str,
                "rating": rating,
                "from_freezer": from_freezer,
                "tags": ", ".join(tags) if tags else "",
                "description": description[:255] if description else "",
                "meal_id": plan.get("meal_id", ""),
            }
            if image and isinstance(image, str) and image.startswith(("https://", "http://")):
                attributes["entity_picture"] = image

            await self._ha.set_state(
                entity_id=entity_id,
                state=title,
                attributes=attributes,
            )
            logger.info("Updated %s = %s", entity_id, title)
        else:
            logger.info(
                "No plan found for %s. Cached dates: %s",
                today_str,
                list(self._plans.keys()),
            )
            await self._ha.set_state(
                entity_id=entity_id,
                state="No meal planned",
                attributes={
                    "friendly_name": "Today's Meal",
                    "icon": "mdi:food-off",
                    "source": "nostr_mealplanner",
                    "date": today_str,
                },
            )
            logger.info("Updated %s = No meal planned", entity_id)

    def _get_meal_title(self, plan: dict) -> str:
        meal_data = plan.get("meal_data", {})
        return meal_data.get("title", "Unknown")

    def _find_date_by_dtag(self, d_tag: str) -> str | None:
        """Find the cached date for a plan by its d-tag (mmp:plan:{id})."""
        plan_id = d_tag.split(":")[-1] if ":" in d_tag else None
        if not plan_id:
            return None
        for plan_date, plan in self._plans.items():
            if plan.get("id") == plan_id:
                return plan_date
        return None

    @staticmethod
    def _is_date_in_window(date_str: str) -> bool:
        """Check if a date string falls within the cache window."""
        try:
            plan_date = date.fromisoformat(date_str)
        except (ValueError, TypeError):
            return False
        today = date.today()
        return today - timedelta(days=_CACHE_WINDOW_DAYS) <= plan_date <= today + timedelta(days=_CACHE_WINDOW_DAYS)

    def _prune_old_plans(self) -> None:
        """Remove cached plans outside the date window."""
        stale = [d for d in self._plans if not self._is_date_in_window(d)]
        for d in stale:
            del self._plans[d]
        if stale:
            logger.debug("Pruned %d stale plan(s) from cache", len(stale))
