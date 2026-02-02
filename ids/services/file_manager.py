"""Safe file operations with backup and rollback"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
from dataclasses import dataclass

from ids.utils import get_logger

logger = get_logger(__name__)


@dataclass
class FileBackup:
    """Information about a file backup"""
    original_path: Path
    backup_path: Path
    timestamp: datetime
    session_id: str


class FileManager:
    """
    Manage file operations with automatic backup and rollback capability.
    All modifications are backed up before changes.
    """
    
    def __init__(self, backup_root: Path):
        """
        Initialize file manager.
        
        Args:
            backup_root: Root directory for backups
        """
        self.backup_root = backup_root
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.backups: Dict[str, FileBackup] = {}
    
    def read_file(self, filepath: Path) -> Optional[str]:
        """
        Read file contents.
        
        Args:
            filepath: Path to file
            
        Returns:
            File contents or None if error
        """
        try:
            return filepath.read_text(encoding='utf-8')
        except Exception as e:
            logger.error("error_reading_file", filepath=str(filepath), error=str(e))
            return None
    
    def write_file(
        self, 
        filepath: Path, 
        content: str, 
        session_id: str,
        create_backup: bool = True
    ) -> bool:
        """
        Write content to file with automatic backup.
        
        Args:
            filepath: Path to file
            content: New file content
            session_id: Session ID for tracking
            create_backup: Whether to backup before writing
            
        Returns:
            True if successful
        """
        try:
            # Create backup if file exists
            if create_backup and filepath.exists():
                backup_success = self._create_backup(filepath, session_id)
                if not backup_success:
                    logger.warning("backup_failed_continuing", filepath=str(filepath))
            
            # Ensure parent directory exists
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temp file first
            temp_path = filepath.with_suffix(filepath.suffix + '.tmp')
            temp_path.write_text(content, encoding='utf-8')
            
            # Atomic move
            temp_path.replace(filepath)
            
            logger.info("file_written", filepath=str(filepath), size=len(content))
            return True
            
        except Exception as e:
            logger.error("error_writing_file", filepath=str(filepath), error=str(e))
            return False
    
    def _create_backup(self, filepath: Path, session_id: str) -> bool:
        """
        Create backup of a file.
        
        Args:
            filepath: File to backup
            session_id: Session ID
            
        Returns:
            True if successful
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self.backup_root / session_id
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup filename: original_name.timestamp.bak
            backup_name = f"{filepath.name}.{timestamp}.bak"
            backup_path = backup_dir / backup_name
            
            # Copy file
            shutil.copy2(filepath, backup_path)
            
            # Track backup
            self.backups[str(filepath)] = FileBackup(
                original_path=filepath,
                backup_path=backup_path,
                timestamp=datetime.now(),
                session_id=session_id
            )
            
            logger.info("backup_created", original=str(filepath), backup=str(backup_path))
            return True
            
        except Exception as e:
            logger.error("error_creating_backup", filepath=str(filepath), error=str(e))
            return False
    
    def rollback_file(self, filepath: Path) -> bool:
        """
        Rollback a file to its backup.
        
        Args:
            filepath: File to rollback
            
        Returns:
            True if successful
        """
        try:
            filepath_str = str(filepath)
            if filepath_str not in self.backups:
                logger.warning("no_backup_found", filepath=filepath_str)
                return False
            
            backup = self.backups[filepath_str]
            
            # Restore from backup
            shutil.copy2(backup.backup_path, backup.original_path)
            
            logger.info("file_rolled_back", 
                       filepath=filepath_str, 
                       backup=str(backup.backup_path))
            return True
            
        except Exception as e:
            logger.error("error_rolling_back", filepath=str(filepath), error=str(e))
            return False
    
    def rollback_session(self, session_id: str) -> int:
        """
        Rollback all files modified in a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Number of files rolled back
        """
        count = 0
        for filepath_str, backup in list(self.backups.items()):
            if backup.session_id == session_id:
                if self.rollback_file(backup.original_path):
                    count += 1
        
        logger.info("session_rolled_back", session_id=session_id, files=count)
        return count
    
    def cleanup_old_backups(self, days: int = 7) -> int:
        """
        Remove backups older than specified days.
        
        Args:
            days: Age threshold in days
            
        Returns:
            Number of backups removed
        """
        count = 0
        cutoff = datetime.now().timestamp() - (days * 86400)
        
        for backup_path in self.backup_root.rglob("*.bak"):
            if backup_path.stat().st_mtime < cutoff:
                backup_path.unlink()
                count += 1
        
        logger.info("old_backups_cleaned", count=count, days=days)
        return count
    
    def list_backups(self, session_id: Optional[str] = None) -> list[FileBackup]:
        """
        List all backups, optionally filtered by session.
        
        Args:
            session_id: Optional session ID filter
            
        Returns:
            List of backups
        """
        if session_id:
            return [b for b in self.backups.values() if b.session_id == session_id]
        return list(self.backups.values())
