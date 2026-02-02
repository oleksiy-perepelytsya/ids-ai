"""Abstract base classes for storage"""

from abc import ABC, abstractmethod
from typing import List, Optional
from ids.models import DevSession, Project


class BaseSessionStore(ABC):
    """Abstract interface for session storage"""
    
    @abstractmethod
    async def create_session(self, session: DevSession) -> DevSession:
        """Create new session"""
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[DevSession]:
        """Get session by ID"""
        pass
    
    @abstractmethod
    async def update_session(self, session: DevSession) -> DevSession:
        """Update existing session"""
        pass
    
    @abstractmethod
    async def get_user_sessions(
        self, 
        telegram_user_id: int, 
        limit: int = 10
    ) -> List[DevSession]:
        """Get recent sessions for user"""
        pass
    
    @abstractmethod
    async def get_active_session(self, telegram_user_id: int) -> Optional[DevSession]:
        """Get user's currently active session"""
        pass


class BaseProjectStore(ABC):
    """Abstract interface for project storage"""
    
    @abstractmethod
    async def create_project(self, project: Project) -> Project:
        """Create new project"""
        pass
    
    @abstractmethod
    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        pass
    
    @abstractmethod
    async def get_project_by_name(
        self, 
        name: str, 
        telegram_user_id: int
    ) -> Optional[Project]:
        """Get project by name for specific user"""
        pass
    
    @abstractmethod
    async def get_user_projects(self, telegram_user_id: int) -> List[Project]:
        """Get all projects for user"""
        pass
    
    @abstractmethod
    async def update_project(self, project: Project) -> Project:
        """Update existing project"""
        pass
