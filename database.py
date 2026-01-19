import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "reminder_bot.db"):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        """Get a database connection"""
        return sqlite3.connect(self.db_path)

    def init_database(self):
        """Initialize database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # User queue table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT UNIQUE,
                first_name TEXT,
                last_name TEXT,
                position INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Active reminders table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                queue_id INTEGER,
                user_id INTEGER NOT NULL,
                username TEXT,
                reminder_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_reminded_at TIMESTAMP,
                next_reminder_at TIMESTAMP
            )
        ''')

        # Reminder history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminder_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')

        # Skip week flag table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS skip_week (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reason TEXT
            )
        ''')
        # Schedule table (single row)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS schedule (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Auto-pop schedule table (single row)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS autopop_schedule (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                day_of_week INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                minute INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Group chat table (single row)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS group_chat (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                chat_id INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.commit()
        self._ensure_active_reminder_columns(cursor)
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")

    def _ensure_active_reminder_columns(self, cursor):
        """Ensure active_reminders has queue_id and username columns, and migrate if possible."""
        cursor.execute("PRAGMA table_info(active_reminders)")
        columns = {row[1] for row in cursor.fetchall()}

        if "queue_id" not in columns:
            cursor.execute("ALTER TABLE active_reminders ADD COLUMN queue_id INTEGER")
            logger.info("Added queue_id column to active_reminders")
        if "username" not in columns:
            cursor.execute("ALTER TABLE active_reminders ADD COLUMN username TEXT")
            logger.info("Added username column to active_reminders")

        # Best-effort migration for a single legacy active reminder
        cursor.execute("SELECT COUNT(*) FROM active_reminders WHERE queue_id IS NULL")
        legacy_count = cursor.fetchone()[0]
        if legacy_count == 1:
            cursor.execute('''
                SELECT id, user_id FROM active_reminders WHERE queue_id IS NULL LIMIT 1
            ''')
            legacy = cursor.fetchone()
            cursor.execute('''
                SELECT id, user_id, username
                FROM user_queue
                ORDER BY position ASC
                LIMIT 1
            ''')
            next_user = cursor.fetchone()

            if legacy and next_user:
                reminder_id, legacy_user_id = legacy
                queue_id, queue_user_id, queue_username = next_user
                if legacy_user_id in (0, queue_user_id):
                    cursor.execute('''
                        UPDATE active_reminders
                        SET queue_id = ?, username = ?
                        WHERE id = ?
                    ''', (queue_id, queue_username, reminder_id))
                    logger.info("Migrated legacy active reminder to queue_id=%s", queue_id)

    def add_user_to_queue(self, user_id: int, username: str = None,
                         first_name: str = None, last_name: str = None) -> bool:
        """Add a user to the queue"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Check if username already exists (for manual additions)
            if username:
                cursor.execute('SELECT user_id FROM user_queue WHERE username = ?', (username,))
                if cursor.fetchone():
                    logger.warning(f"Username @{username} already in queue")
                    return False

            # Get the next position
            cursor.execute('SELECT MAX(position) FROM user_queue')
            max_pos = cursor.fetchone()[0]
            next_position = (max_pos + 1) if max_pos is not None else 0

            cursor.execute('''
                INSERT INTO user_queue (user_id, username, first_name, last_name, position)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, next_position))

            conn.commit()
            logger.info(f"Added user {user_id} (@{username}) to queue at position {next_position}")
            return True
        except sqlite3.IntegrityError as e:
            # This will catch duplicate username errors (UNIQUE constraint on username)
            logger.warning(f"Failed to add user {user_id} (@{username}): {e}")
            return False
        finally:
            conn.close()

    def remove_user_from_queue(self, user_id: int) -> bool:
        """Remove a user from the queue"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT position FROM user_queue WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            if not result:
                return False

            removed_position = result[0]

            # Remove the user
            cursor.execute('DELETE FROM user_queue WHERE user_id = ?', (user_id,))

            # Reorder remaining users
            cursor.execute('''
                UPDATE user_queue
                SET position = position - 1
                WHERE position > ?
            ''', (removed_position,))

            conn.commit()
            logger.info(f"Removed user {user_id} from queue")
            return True
        finally:
            conn.close()

    def get_next_user(self) -> Optional[Tuple[int, int, str, str, str]]:
        """Get the next user in queue (lowest position)"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, user_id, username, first_name, last_name
                FROM user_queue
                ORDER BY position ASC
                LIMIT 1
            ''')

            result = cursor.fetchone()
            return result
        finally:
            conn.close()

    def move_user_to_back(self, user_id: int) -> bool:
        """Move a user from front to back of queue"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get current position
            cursor.execute('SELECT position FROM user_queue WHERE user_id = ? LIMIT 1', (user_id,))
            result = cursor.fetchone()

            if not result:
                return False

            current_position = result[0]

            # Get max position
            cursor.execute('SELECT MAX(position) FROM user_queue')
            max_position = cursor.fetchone()[0]

            if max_position is None or current_position == max_position:
                return True  # Already at back or only user

            # Move everyone between current and end up by 1
            cursor.execute('''
                UPDATE user_queue
                SET position = position - 1
                WHERE position > ?
            ''', (current_position,))

            # Move user to back (use LIMIT 1 to avoid updating multiple rows with same user_id)
            cursor.execute('''
                UPDATE user_queue
                SET position = ?
                WHERE user_id = ?
                AND position = ?
            ''', (max_position, user_id, current_position))

            conn.commit()
            logger.info(f"Moved user {user_id} to back of queue")
            return True
        finally:
            conn.close()

    def move_user_to_back_by_queue_id(self, queue_id: int) -> bool:
        """Move a user from front to back of queue using internal queue ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Get current position using queue ID
            cursor.execute('SELECT position FROM user_queue WHERE id = ?', (queue_id,))
            result = cursor.fetchone()

            if not result:
                return False

            current_position = result[0]

            # Get max position
            cursor.execute('SELECT MAX(position) FROM user_queue')
            max_position = cursor.fetchone()[0]

            if max_position is None or current_position == max_position:
                return True  # Already at back or only user

            # Move everyone between current and end forward by 1 position (decrease their position)
            # IMPORTANT: Exclude the current user by using id != queue_id
            cursor.execute('''
                UPDATE user_queue
                SET position = position - 1
                WHERE position > ? AND id != ?
            ''', (current_position, queue_id))

            # Move user to back using queue ID
            # After decrementing everyone else, the positions have shifted down by 1
            # So the new max position is max_position - 1, but we want to place our user
            # at the end, which is now at the old max_position - 1
            # Actually, simpler: just set to max_position. Since we excluded this user from
            # the decrement, and decremented everyone else, the final state will be correct.
            # Wait, that's still wrong. Let's think step by step:
            # Original: [user1@0, user2@1, user3@2] (max=2)
            # Decrement positions > 0 (excluding user1): [user1@0, user2@0, user3@1]
            # Set user1 to max (2): [user1@2, user2@0, user3@1]
            # Final after reorder: [user2@0, user3@1, user1@2] ✓
            # This is correct!
            cursor.execute('''
                UPDATE user_queue
                SET position = ?
                WHERE id = ?
            ''', (max_position, queue_id))

            conn.commit()
            logger.info(f"Moved queue entry {queue_id} from position {current_position} to back (position {max_position})")
            return True
        finally:
            conn.close()

    def get_queue_list(self) -> List[Tuple[int, int, str, str, str, int]]:
        """Get all users in queue ordered by position
        Returns: List of tuples (queue_id, user_id, username, first_name, last_name, position)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, user_id, username, first_name, last_name, position
                FROM user_queue
                ORDER BY position ASC
            ''')
            return cursor.fetchall()
        finally:
            conn.close()

    def clear_queue(self):
        """Clear all users from the queue"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM user_queue')
            conn.commit()
            logger.info("Queue cleared")
        finally:
            conn.close()

    def create_reminder(self, queue_id: int, user_id: int, username: str,
                        next_reminder_at: Optional[datetime]) -> int:
        """Create a new active reminder for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            now = datetime.now()
            cursor.execute('''
                INSERT INTO active_reminders
                (queue_id, user_id, username, reminder_count, created_at, last_reminded_at, next_reminder_at)
                VALUES (?, ?, ?, 0, ?, ?, ?)
            ''', (queue_id, user_id, username, now, now, next_reminder_at))

            reminder_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Created reminder {reminder_id} for user {user_id}")
            return reminder_id
        finally:
            conn.close()

    def get_active_reminder(self, queue_id: Optional[int] = None,
                            user_id: Optional[int] = None,
                            username: Optional[str] = None) -> Optional[Tuple[int, int, datetime, datetime]]:
        """Get active reminder for a user/queue entry"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if queue_id is not None:
                cursor.execute('''
                    SELECT id, reminder_count, last_reminded_at, next_reminder_at
                    FROM active_reminders
                    WHERE queue_id = ?
                ''', (queue_id,))
            elif user_id is not None and user_id != 0:
                cursor.execute('''
                    SELECT id, reminder_count, last_reminded_at, next_reminder_at
                    FROM active_reminders
                    WHERE user_id = ?
                ''', (user_id,))
            elif username:
                cursor.execute('''
                    SELECT id, reminder_count, last_reminded_at, next_reminder_at
                    FROM active_reminders
                    WHERE username = ?
                ''', (username,))
            else:
                return None

            row = cursor.fetchone()
            if not row:
                return None

            reminder_id, reminder_count, last_reminded_at, next_reminder_at = row
            if isinstance(last_reminded_at, str):
                last_reminded_at = datetime.fromisoformat(last_reminded_at)
            if isinstance(next_reminder_at, str):
                next_reminder_at = datetime.fromisoformat(next_reminder_at)

            return (reminder_id, reminder_count, last_reminded_at, next_reminder_at)
        finally:
            conn.close()

    def get_active_reminders(self) -> List[Tuple[int, Optional[int], int, Optional[str], int]]:
        """Get all active reminders"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT id, queue_id, user_id, username, reminder_count
                FROM active_reminders
            ''')
            return cursor.fetchall()
        finally:
            conn.close()

    def update_reminder(self, reminder_id: int, reminder_count: int,
                       last_reminded_at: datetime, next_reminder_at: datetime):
        """Update an active reminder"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE active_reminders
                SET reminder_count = ?,
                    last_reminded_at = ?,
                    next_reminder_at = ?
                WHERE id = ?
            ''', (reminder_count, last_reminded_at, next_reminder_at, reminder_id))

            conn.commit()
            logger.info(f"Updated reminder {reminder_id}")
        finally:
            conn.close()

    def delete_reminder(self, reminder_id: int):
        """Delete an active reminder"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM active_reminders WHERE id = ?', (reminder_id,))
            conn.commit()
            logger.info(f"Deleted reminder {reminder_id}")
        finally:
            conn.close()

    def add_history(self, user_id: int, action: str, notes: str = None):
        """Add a reminder history entry"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO reminder_history (user_id, action, notes)
                VALUES (?, ?, ?)
            ''', (user_id, action, notes))

            conn.commit()
        finally:
            conn.close()

    def get_user_history(self, user_id: int, limit: int = 10) -> List[Tuple]:
        """Get reminder history for a user"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT action, timestamp, notes
                FROM reminder_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))

            return cursor.fetchall()
        finally:
            conn.close()

    def set_skip_week(self, reason: str = "Admin skipped week via /noreview"):
        """Set flag to skip this week's reminder"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO skip_week (reason)
                VALUES (?)
            ''', (reason,))

            conn.commit()
            logger.info(f"Skip week flag set: {reason}")
        finally:
            conn.close()

    def is_week_skipped(self) -> bool:
        """Check if this week should be skipped"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('SELECT COUNT(*) FROM skip_week')
            count = cursor.fetchone()[0]
            return count > 0
        finally:
            conn.close()

    def clear_skip_week(self):
        """Clear the skip week flag"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM skip_week')
            conn.commit()
            logger.info("Skip week flag cleared")
        finally:
            conn.close()

    def set_schedule(self, day_of_week: int, hour: int, minute: int):
        """Persist the reminder schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO schedule (id, day_of_week, hour, minute, updated_at)
                VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    day_of_week = excluded.day_of_week,
                    hour = excluded.hour,
                    minute = excluded.minute,
                    updated_at = excluded.updated_at
            ''', (day_of_week, hour, minute))
            conn.commit()
            logger.info("Saved schedule: day=%s hour=%s minute=%s", day_of_week, hour, minute)
        finally:
            conn.close()

    def get_schedule(self) -> Optional[Tuple[int, int, int]]:
        """Get persisted schedule, if any"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT day_of_week, hour, minute
                FROM schedule
                WHERE id = 1
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return row if row else None
        finally:
            conn.close()

    def set_autopop_schedule(self, day_of_week: int, hour: int, minute: int):
        """Persist the auto-pop schedule"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO autopop_schedule (id, day_of_week, hour, minute, updated_at)
                VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    day_of_week = excluded.day_of_week,
                    hour = excluded.hour,
                    minute = excluded.minute,
                    updated_at = excluded.updated_at
            ''', (day_of_week, hour, minute))
            conn.commit()
            logger.info("Saved auto-pop schedule: day=%s hour=%s minute=%s", day_of_week, hour, minute)
        finally:
            conn.close()

    def get_autopop_schedule(self) -> Optional[Tuple[int, int, int]]:
        """Get persisted auto-pop schedule, if any"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT day_of_week, hour, minute
                FROM autopop_schedule
                WHERE id = 1
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return row if row else None
        finally:
            conn.close()

    def find_queue_id(self, user_id: int, username: Optional[str]) -> Optional[int]:
        """Find queue_id by user_id or username"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            if user_id:
                cursor.execute('SELECT id FROM user_queue WHERE user_id = ? LIMIT 1', (user_id,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            if username:
                cursor.execute('SELECT id FROM user_queue WHERE username = ? LIMIT 1', (username,))
                row = cursor.fetchone()
                if row:
                    return row[0]
            return None
        finally:
            conn.close()

    def set_group_chat_id(self, chat_id: int):
        """Persist the group chat ID"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO group_chat (id, chat_id, updated_at)
                VALUES (1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    updated_at = excluded.updated_at
            ''', (chat_id,))
            conn.commit()
            logger.info("Saved group chat ID: %s", chat_id)
        finally:
            conn.close()

    def get_group_chat_id(self) -> Optional[int]:
        """Get persisted group chat ID, if any"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT chat_id
                FROM group_chat
                WHERE id = 1
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
