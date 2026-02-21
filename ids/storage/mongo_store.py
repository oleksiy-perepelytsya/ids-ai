"""MongoDB storage implementation"""

from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from ids.models import DevSession, Project, SessionStatus
from ids.config import settings
from ids.utils import get_logger
from .base import BaseSessionStore, BaseProjectStore

logger = get_logger(__name__)


class MongoSessionStore(BaseSessionStore):
    """MongoDB implementation of session storage"""

    def __init__(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db]
        self.sessions = self.db.sessions

    async def create_session(self, session: DevSession) -> DevSession:
        """Create new session"""
        session_dict = session.model_dump()
        await self.sessions.insert_one(session_dict)
        logger.info(
            "session_created",
            session_id=session.session_id,
            user_id=session.telegram_user_id
        )
        return session

    async def get_session(self, session_id: str) -> Optional[DevSession]:
        """Get session by ID"""
        doc = await self.sessions.find_one({"session_id": session_id})
        if doc:
            doc.pop("_id", None)  # Remove MongoDB ID
            return DevSession(**doc)
        return None

    async def update_session(self, session: DevSession) -> DevSession:
        """Update existing session"""
        session_dict = session.model_dump()
        await self.sessions.replace_one(
            {"session_id": session.session_id},
            session_dict
        )
        logger.info(
            "session_updated",
            session_id=session.session_id,
            status=session.status
        )
        return session

    async def get_user_sessions(
        self,
        telegram_user_id: int,
        project_id: str,
        limit: int = 10
    ) -> List[DevSession]:
        """Get recent sessions for user filtered by project"""
        cursor = self.sessions.find(
            {
                "telegram_user_id": telegram_user_id,
                "project_id": project_id
            }
        ).sort("created_at", -1).limit(limit)

        sessions = []
        async for doc in cursor:
            doc.pop("_id", None)
            sessions.append(DevSession(**doc))

        return sessions

    async def delete_project_sessions(self, project_id: str) -> int:
        """Delete all sessions for a project"""
        result = await self.sessions.delete_many({"project_id": project_id})
        logger.info("project_sessions_deleted", project_id=project_id, count=result.deleted_count)
        return result.deleted_count

    async def get_active_session(self, telegram_user_id: int, project_id: str) -> Optional[DevSession]:
        """Get user's currently active session for a project"""
        doc = await self.sessions.find_one({
            "telegram_user_id": telegram_user_id,
            "project_id": project_id,
            "status": {"$in": [
                SessionStatus.PENDING,
                SessionStatus.CLARIFYING,
                SessionStatus.DELIBERATING,
                SessionStatus.AWAITING_CONTINUATION,
                SessionStatus.DEAD_END
            ]}
        })

        if doc:
            doc.pop("_id", None)
            return DevSession(**doc)
        return None


class MongoProjectStore(BaseProjectStore):
    """MongoDB implementation of project storage"""

    def __init__(self):
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db]
        self.projects = self.db.projects

    async def create_project(self, project: Project) -> Project:
        """Create new project"""
        project_dict = project.model_dump()
        await self.projects.insert_one(project_dict)
        logger.info(
            "project_created",
            project_id=project.project_id,
            name=project.name,
            user_id=project.telegram_user_id
        )
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        """Get project by ID"""
        doc = await self.projects.find_one({"project_id": project_id})
        if doc:
            doc.pop("_id", None)
            return Project(**doc)
        return None

    async def get_project_by_name(
        self,
        name: str,
        telegram_user_id: int
    ) -> Optional[Project]:
        """Get project by name for specific user"""
        doc = await self.projects.find_one({
            "name": name,
            "telegram_user_id": telegram_user_id
        })
        if doc:
            doc.pop("_id", None)
            return Project(**doc)
        return None

    async def get_user_projects(self, telegram_user_id: int) -> List[Project]:
        """Get all projects for user"""
        cursor = self.projects.find(
            {"telegram_user_id": telegram_user_id}
        ).sort("name", 1)

        projects = []
        async for doc in cursor:
            doc.pop("_id", None)
            projects.append(Project(**doc))

        return projects

    async def delete_project(self, project_id: str) -> bool:
        """Delete a project document"""
        result = await self.projects.delete_one({"project_id": project_id})
        logger.info("project_deleted", project_id=project_id)
        return result.deleted_count > 0

    async def update_project(self, project: Project) -> Project:
        """Update existing project"""
        project_dict = project.model_dump()
        await self.projects.replace_one(
            {"project_id": project.project_id},
            project_dict
        )
        logger.info(
            "project_updated",
            project_id=project.project_id
        )
        return project
