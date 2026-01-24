"""
Analytics and metrics collection.

Aggregate stats for v1: games played, unique users.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Dict
from collections import defaultdict
import logging


logger = logging.getLogger(__name__)


@dataclass
class DailyStats:
    """Statistics for a single day."""
    games_played: int = 0
    unique_users: set = field(default_factory=set)
    ad_views: int = 0
    ad_clicks: int = 0
    
    @property
    def unique_user_count(self) -> int:
        return len(self.unique_users)


class Analytics:
    """In-memory analytics collector."""
    
    def __init__(self):
        self._daily_stats: Dict[date, DailyStats] = defaultdict(DailyStats)
        self._all_time_games = 0
        self._all_time_users: set = set()
    
    def _get_today(self) -> date:
        return datetime.now().date()
    
    def record_game_played(self, user_id: int) -> None:
        """Record a completed game."""
        today = self._get_today()
        
        self._daily_stats[today].games_played += 1
        self._daily_stats[today].unique_users.add(user_id)
        
        self._all_time_games += 1
        self._all_time_users.add(user_id)
        
        logger.debug(f"Recorded game for user {user_id}")
    
    def record_user_activity(self, user_id: int) -> None:
        """Record user activity (bot start, menu access, etc)."""
        today = self._get_today()
        
        self._daily_stats[today].unique_users.add(user_id)
        self._all_time_users.add(user_id)
    
    def record_ad_view(self) -> None:
        """Record an ad view (v1.5 placeholder)."""
        today = self._get_today()
        self._daily_stats[today].ad_views += 1
    
    def record_ad_click(self) -> None:
        """Record an ad click (v1.5 placeholder)."""
        today = self._get_today()
        self._daily_stats[today].ad_clicks += 1
    
    def get_today_stats(self) -> Dict:
        """Get today's stats."""
        today = self._get_today()
        stats = self._daily_stats[today]
        return {
            "games_played": stats.games_played,
            "unique_users": stats.unique_user_count,
            "ad_views": stats.ad_views,
            "ad_clicks": stats.ad_clicks,
        }
    
    def get_all_time_stats(self) -> Dict:
        """Get all-time stats."""
        return {
            "total_games": self._all_time_games,
            "total_users": len(self._all_time_users),
        }
    
    def get_summary(self) -> str:
        """Get formatted summary for admin display."""
        today = self.get_today_stats()
        all_time = self.get_all_time_stats()
        
        return (
            f"📊 *Статистика*\n\n"
            f"*Сегодня:*\n"
            f"• Игр сыграно: {today['games_played']}\n"
            f"• Уникальных игроков: {today['unique_users']}\n\n"
            f"*Всего:*\n"
            f"• Игр сыграно: {all_time['total_games']}\n"
            f"• Уникальных игроков: {all_time['total_users']}"
        )


# Global analytics instance
analytics = Analytics()


# Convenience functions
def record_game(user_id: int) -> None:
    analytics.record_game_played(user_id)


def record_activity(user_id: int) -> None:
    analytics.record_user_activity(user_id)


def get_stats_summary() -> str:
    return analytics.get_summary()
