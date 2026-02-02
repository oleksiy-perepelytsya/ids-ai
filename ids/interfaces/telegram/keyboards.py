"""Telegram inline keyboards for user interactions"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List
from ids.models import Project


class TelegramKeyboards:
    """Factory for Telegram inline keyboards"""
    
    @staticmethod
    def dead_end_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for dead-end situation"""
        keyboard = [
            [InlineKeyboardButton("💬 Provide Feedback", callback_data="dead_end:feedback")],
            [InlineKeyboardButton("🔄 Restart Fresh", callback_data="dead_end:restart")],
            [InlineKeyboardButton("❌ Cancel", callback_data="session:cancel")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def project_list_keyboard(projects: List[Project]) -> InlineKeyboardMarkup:
        """Keyboard for selecting a project"""
        keyboard = []
        
        for project in projects:
            keyboard.append([
                InlineKeyboardButton(
                    f"📂 {project.name}",
                    callback_data=f"project:select:{project.project_id}"
                )
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def settings_keyboard(round_logging: bool) -> InlineKeyboardMarkup:
        """Keyboard for settings"""
        logging_status = "ON ✅" if round_logging else "OFF ⭕"
        
        keyboard = [
            [InlineKeyboardButton(
                f"Round Logging: {logging_status}",
                callback_data="settings:toggle_logging"
            )],
            [InlineKeyboardButton("🔙 Back", callback_data="settings:close")]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def session_continue_keyboard() -> InlineKeyboardMarkup:
        """Keyboard for continuing a session"""
        keyboard = [
            [InlineKeyboardButton("✅ Continue", callback_data="session:continue")],
            [InlineKeyboardButton("❌ Cancel", callback_data="session:cancel")]
        ]
        return InlineKeyboardMarkup(keyboard)
