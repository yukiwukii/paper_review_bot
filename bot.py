import os
import logging
from datetime import datetime
from typing import Optional, List
from telegram import Update, Chat
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz
from dotenv import load_dotenv

from database import Database

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize database
db = Database()

# Store group chat ID for reminders
GROUP_CHAT_ID = None


class ReminderBot:
    def __init__(self, token: str, timezone: str = "UTC", admin_ids: List[int] = None):
        self.token = token
        self.timezone = pytz.timezone(timezone)
        self.application = None
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)
        self.admin_ids = set(admin_ids) if admin_ids else set()
        self.group_chat_id = None

    def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin"""
        return user_id in self.admin_ids

    async def is_group_admin(self, update: Update, user_id: int) -> bool:
        """Check if user is a group admin"""
        if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
            try:
                member = await update.effective_chat.get_member(user_id)
                return member.status in ['creator', 'administrator']
            except Exception as e:
                logger.error(f"Error checking admin status: {e}")
                return False
        return False

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        is_admin = self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)

        base_commands = (
            "Welcome to the Reminder Bot!\n\n"
            "Available commands:\n"
            "/queue - View the current queue\n"
            "/skip - Skip your turn and pass to next person\n"
            "/help - Show this help message"
        )

        admin_commands = (
            "\n\nAdmin commands:\n"
            "/adduser @username - Add user to queue by username\n"
            "/removeuser @username - Remove user from queue\n"
            "/initqueue @user1 @user2 @user3 - Initialize queue with users\n"
            "/setgroup - Set this group as the reminder target\n"
            "/setschedule <day> <hour> <minute> - Set reminder schedule\n"
            "/setautopop <day> <hour> <minute> - Set auto-pop schedule\n"
            "/clearqueue - Clear the entire queue\n"
            "/noreview - Skip this week's reminder (queue stays the same)\n"
            "/nextreminder - Show next reminder time and who is up next"
        )

        message = base_commands + (admin_commands if is_admin else "")
        await update.message.reply_text(message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        is_admin = self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)

        base_help = (
            "Reminder Bot Commands:\n\n"
            "/queue - View the current queue\n"
            "/skip - Skip your turn and pass to next person\n"
            "/help - Show this help message\n\n"
            "How it works:\n"
            "1. Admins add users to the queue\n"
            "2. Every week, the bot reminds the next person in the group\n"
            "3. Use /skip to pass your turn to the next person\n"
            "4. After the auto-pop schedule, you'll be moved to the back of the queue"
        )

        admin_help = (
            "\n\nAdmin Commands:\n"
            "/adduser @username - Add a user to the queue by their username\n"
            "/removeuser @username - Remove a user from the queue\n"
            "/initqueue @user1 @user2 @user3 - Initialize/replace the entire queue\n"
            "/setgroup - Set this group chat as the reminder target\n"
            "/setschedule <day> <hour> <minute> - Set reminder schedule (day: 0=Mon, 6=Sun)\n"
            "/setautopop <day> <hour> <minute> - Set auto-pop schedule (day: 0=Mon, 6=Sun)\n"
            "/clearqueue - Clear the entire queue\n"
            "/noreview - Skip this week's reminder (queue order unchanged)\n"
            "/nextreminder - Show next reminder time and who is up next\n\n"
            "Note: Users must be in the group for the bot to remind them!"
        )

        message = base_help + (admin_help if is_admin else "")
        await update.message.reply_text(message)

    async def setgroup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set the current group as the reminder target"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if update.effective_chat.type not in [Chat.GROUP, Chat.SUPERGROUP]:
            await update.message.reply_text("This command can only be used in a group chat.")
            return

        self.group_chat_id = update.effective_chat.id
        db.set_group_chat_id(self.group_chat_id)
        await update.message.reply_text(
            f"Group chat set! Reminders will be sent to this group.\n"
            f"Group ID: {self.group_chat_id}"
        )
        logger.info(f"Group chat set to {self.group_chat_id}")

    async def adduser_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a user to the queue by username"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /adduser @username\n"
                "Example: /adduser @john"
            )
            return

        username = context.args[0].lstrip('@')

        try:
            # Try to get user info from the chat
            chat_member = None
            if update.effective_chat.type in [Chat.GROUP, Chat.SUPERGROUP]:
                # In groups, we need to find the user by their username
                # Unfortunately, we can't directly lookup by username
                # So we'll store with username and resolve when sending reminders
                pass

            # Add to queue with username (user_id will be 0 as placeholder)
            # We'll resolve the actual user_id when sending reminders
            success = db.add_user_to_queue(
                user_id=0,  # Placeholder, will be resolved later
                username=username,
                first_name=None,
                last_name=None
            )

            if success:
                queue = db.get_queue_list()
                position = len(queue)
                await update.message.reply_text(
                    f"Added @{username} to the queue at position {position}!"
                )
                db.add_history(0, "added_by_admin", f"Username: @{username}, Position: {position}")
            else:
                await update.message.reply_text(
                    f"@{username} is already in the queue."
                )
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            await update.message.reply_text(f"Error adding user: {e}")

    async def removeuser_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a user from the queue by username"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /removeuser @username\n"
                "Example: /removeuser @john"
            )
            return

        username = context.args[0].lstrip('@')

        # Find user by username
        queue = db.get_queue_list()
        user_found = False

        for qid, uid, uname, first_name, last_name, position in queue:
            if uname == username:
                success = db.remove_user_from_queue(uid)
                if success:
                    await update.message.reply_text(f"Removed @{username} from the queue.")
                    db.add_history(uid, "removed_by_admin", f"Username: @{username}")
                    user_found = True
                    break

        if not user_found:
            await update.message.reply_text(f"@{username} not found in the queue.")

    async def initqueue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Initialize/replace the queue with a list of usernames"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if not context.args or len(context.args) < 1:
            await update.message.reply_text(
                "Usage: /initqueue @user1 @user2 @user3\n"
                "Example: /initqueue @alice @bob @charlie\n\n"
                "This will replace the entire queue with the provided users."
            )
            return

        # Log what we received for debugging
        logger.info(f"initqueue received {len(context.args)} args: {context.args}")

        # Clear existing queue
        db.clear_queue()

        # Add users in order
        added_users = []
        for username_arg in context.args:
            username = username_arg.lstrip('@')
            logger.info(f"Processing username: {username}")
            success = db.add_user_to_queue(
                user_id=0,  # Placeholder
                username=username,
                first_name=None,
                last_name=None
            )
            if success:
                added_users.append(f"@{username}")
            else:
                logger.warning(f"Failed to add {username} to queue")

        if added_users:
            await update.message.reply_text(
                f"Queue initialized with {len(added_users)} users:\n" +
                "\n".join([f"{i+1}. {u}" for i, u in enumerate(added_users)])
            )
            db.add_history(0, "queue_initialized", f"Users: {', '.join(added_users)}")
        else:
            await update.message.reply_text("No users were added to the queue.")

    async def clearqueue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Clear the entire queue"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        db.clear_queue()
        await update.message.reply_text("Queue cleared successfully.")
        db.add_history(0, "queue_cleared", "All users removed from queue")

    async def noreview_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Skip this week's reminder without changing the queue"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        # Get the next user in queue
        next_user = db.get_next_user()

        if not next_user:
            await update.message.reply_text("The queue is empty. Nothing to skip.")
            return

        queue_id, user_id, username, first_name, last_name = next_user
        name = username or first_name or f"User {user_id}"

        # Check if there's an active reminder for this user
        active_reminder = db.get_active_reminder(queue_id=queue_id, user_id=user_id, username=username)

        if active_reminder:
            reminder_id, reminder_count, last_reminded_at, next_reminder_at = active_reminder
            # Delete the active reminder
            db.delete_reminder(reminder_id)
            db.add_history(user_id or 0, "review_skipped", f"Admin cancelled active reminder via /noreview")
            await update.message.reply_text(
                f"✓ Cancelled active reminder for @{name}.\n"
                f"✓ Set skip flag to prevent next scheduled reminder.\n\n"
                "This week's review has been skipped. Queue order remains unchanged."
            )
        else:
            # No active reminder yet, set flag to skip next scheduled reminder
            await update.message.reply_text(
                f"✓ Set skip flag to prevent next scheduled reminder for @{name}.\n\n"
                "This week's review will be skipped. Queue order remains unchanged."
            )

        # Set the skip week flag
        db.set_skip_week(f"Admin {update.effective_user.id} used /noreview")
        db.add_history(0, "week_skipped", f"Admin {update.effective_user.id} skipped week via /noreview")

        logger.info(f"Admin {update.effective_user.id} used /noreview command")

    async def nextreminder_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show next scheduled reminder time and next user in queue"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        job = self.scheduler.get_job('weekly_reminder')
        next_run = job.next_run_time if job else None
        if next_run:
            next_run = next_run.astimezone(self.timezone)
            next_run_text = next_run.strftime("%Y-%m-%d %H:%M:%S %Z")
        else:
            next_run_text = "Not scheduled"

        queue = db.get_queue_list()
        active_index = None
        active_name = "none"
        for idx, (qid, uid, username, first_name, last_name, position) in enumerate(queue):
            active_reminder = db.get_active_reminder(queue_id=qid, user_id=uid, username=username)
            if active_reminder:
                active_index = idx
                active_name = f"{username}" if username else (first_name or f"User {uid}")
                break

        next_name = "none"
        if queue:
            if active_index is None:
                # No active reminder; next up is the front of the queue
                qid, uid, username, first_name, last_name, position = queue[0]
                next_name = f"{username}" if username else (first_name or f"User {uid}")
            elif active_index + 1 < len(queue):
                qid, uid, username, first_name, last_name, position = queue[active_index + 1]
                next_name = f"{username}" if username else (first_name or f"User {uid}")

        skip_note = ""
        if db.is_week_skipped():
            skip_note = "\nNote: /noreview is set, so the next scheduled run will be skipped."

        this_week_text = "done" if active_name == "none" else active_name
        await update.message.reply_text(
            f"This week's review is {this_week_text}\n"
            f"Next reminder is at {next_run_text} for {next_name}"
            f"{skip_note}"
        )

    async def setautopop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set the auto-pop schedule"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /setautopop <day> <hour> <minute>\n\n"
                "Day: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday\n"
                "Hour: 0-23 (24-hour format)\n"
                "Minute: 0-59\n\n"
                "Example: /setautopop 0 18 0\n"
                "(Sets auto-pop for Monday at 6:00 PM)"
            )
            return

        try:
            day_of_week = int(context.args[0])
            hour = int(context.args[1])
            minute = int(context.args[2])

            if not (0 <= day_of_week <= 6):
                await update.message.reply_text("Day must be between 0 (Monday) and 6 (Sunday)")
                return
            if not (0 <= hour <= 23):
                await update.message.reply_text("Hour must be between 0 and 23")
                return
            if not (0 <= minute <= 59):
                await update.message.reply_text("Minute must be between 0 and 59")
                return

            self.scheduler.remove_job('autopop_reminder')
            self.scheduler.add_job(
                self.handle_autopop,
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day_of_week=day_of_week,
                    timezone=self.timezone
                ),
                id='autopop_reminder',
                name='Auto-Pop Reminder',
                replace_existing=True
            )
            db.set_autopop_schedule(day_of_week, hour, minute)

            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = days[day_of_week]
            await update.message.reply_text(
                f"Auto-pop schedule updated!\n"
                f"Users with active reminders will be auto-popped every {day_name} at {hour:02d}:{minute:02d} ({self.timezone})"
            )
            logger.info(f"Auto-pop schedule updated: {day_name} at {hour:02d}:{minute:02d}")

        except ValueError:
            await update.message.reply_text("Invalid input. Please use numbers only.")
        except Exception as e:
            logger.error(f"Error setting auto-pop schedule: {e}")
            await update.message.reply_text(f"Error setting auto-pop schedule: {e}")

    async def setschedule_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set the reminder schedule"""
        if not (self.is_admin(update.effective_user.id) or await self.is_group_admin(update, update.effective_user.id)):
            await update.message.reply_text("Only admins can use this command.")
            return

        if not context.args or len(context.args) < 3:
            await update.message.reply_text(
                "Usage: /setschedule <day> <hour> <minute>\n\n"
                "Day: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday, 5=Saturday, 6=Sunday\n"
                "Hour: 0-23 (24-hour format)\n"
                "Minute: 0-59\n\n"
                "Example: /setschedule 0 9 0\n"
                "(Sets reminder for Monday at 9:00 AM)"
            )
            return

        try:
            day_of_week = int(context.args[0])
            hour = int(context.args[1])
            minute = int(context.args[2])

            # Validate inputs
            if not (0 <= day_of_week <= 6):
                await update.message.reply_text("Day must be between 0 (Monday) and 6 (Sunday)")
                return
            if not (0 <= hour <= 23):
                await update.message.reply_text("Hour must be between 0 and 23")
                return
            if not (0 <= minute <= 59):
                await update.message.reply_text("Minute must be between 0 and 59")
                return

            # Remove old job and create new one
            self.scheduler.remove_job('weekly_reminder')
            self.scheduler.add_job(
                self.send_weekly_reminder,
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day_of_week=day_of_week,
                    timezone=self.timezone
                ),
                id='weekly_reminder',
                name='Weekly Reminder',
                replace_existing=True
            )
            db.set_schedule(day_of_week, hour, minute)

            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_name = days[day_of_week]

            await update.message.reply_text(
                f"Schedule updated!\n"
                f"Reminders will be sent every {day_name} at {hour:02d}:{minute:02d} ({self.timezone})"
            )
            logger.info(f"Schedule updated: {day_name} at {hour:02d}:{minute:02d}")

        except ValueError:
            await update.message.reply_text("Invalid input. Please use numbers only.")
        except Exception as e:
            logger.error(f"Error setting schedule: {e}")
            await update.message.reply_text(f"Error setting schedule: {e}")

    async def queue_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /queue command - show current queue"""
        queue = db.get_queue_list()

        if not queue:
            await update.message.reply_text("The queue is empty.")
            return

        message = "Current Queue:\n\n"
        user_id = update.effective_user.id

        for idx, (qid, uid, username, first_name, last_name, position) in enumerate(queue, 1):
            name = first_name or username or f"User {uid}"
            marker = " 👈 (you)" if uid == user_id else ""

            # Check if user has active reminder
            active_reminder = db.get_active_reminder(queue_id=qid, user_id=uid, username=username)
            if active_reminder:
                marker += " 🔔"

            message += f"{idx}. {name}{marker}\n"

        await update.message.reply_text(message)

    async def skip_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /skip command - skip turn and move to next person"""
        user = update.effective_user

        queue = db.get_queue_list()
        queue_id = None
        user_id_in_queue = None
        username_in_queue = None

        # Find queue entry by user_id first, then by username
        for qid, uid, uname, first_name, last_name, position in queue:
            if uid == user.id and uid != 0:
                queue_id = qid
                user_id_in_queue = uid
                username_in_queue = uname
                break

        if queue_id is None and user.username:
            for qid, uid, uname, first_name, last_name, position in queue:
                if uname and uname.lower() == user.username.lower():
                    queue_id = qid
                    user_id_in_queue = uid
                    username_in_queue = uname
                    break

        active_reminder = None
        if queue_id is not None:
            active_reminder = db.get_active_reminder(queue_id=queue_id, user_id=user_id_in_queue, username=username_in_queue)

        if not active_reminder:
            await update.message.reply_text(
                "You don't have an active reminder to skip."
            )
            return

        reminder_id, reminder_count, last_reminded_at, next_reminder_at = active_reminder

        # Delete the current reminder
        db.delete_reminder(reminder_id)

        # Move user to back of queue
        db.move_user_to_back_by_queue_id(queue_id)

        # Add to history
        db.add_history(user_id_in_queue or 0, "skipped", f"User skipped their turn (@{user.username})")

        await update.message.reply_text(
            "You've skipped your turn. Moving to the next person in queue."
        )

        logger.info(f"User {user.id} (@{user.username}) skipped their turn")

        # Immediately remind the next person
        await self.send_weekly_reminder()

    async def send_weekly_reminder(self):
        """Send reminder to the next person in queue"""
        # Check if this week should be skipped
        if db.is_week_skipped():
            logger.info("Week is skipped due to /noreview flag, clearing flag")
            db.clear_skip_week()

            # Notify in group if set
            if self.group_chat_id:
                try:
                    await self.application.bot.send_message(
                        chat_id=self.group_chat_id,
                        text="📋 This week's review has been skipped as requested. "
                             "Normal schedule will resume next week."
                    )
                except Exception as e:
                    logger.error(f"Failed to send skip notification to group: {e}")
            return

        next_user = db.get_next_user()

        if not next_user:
            logger.info("No users in queue to remind")
            return

        queue_id, user_id, username, first_name, last_name = next_user

        # Check if this user already has an active reminder
        active_reminder = db.get_active_reminder(queue_id=queue_id, user_id=user_id, username=username)

        # Send reminder message to group chat if set
        if self.group_chat_id:
            # Send to group with @mention
            mention = f"@{username}" if username else f"User {user_id}"
            message = (
                f"{mention} 🔔\n\n"
                "It's your turn for paper review!\n\n"
                "Please use /skip to pass to the next person."
            )

            try:
                await self.application.bot.send_message(chat_id=self.group_chat_id, text=message)
                if active_reminder:
                    reminder_id, reminder_count, last_reminded_at, next_reminder_at = active_reminder
                    db.update_reminder(reminder_id, reminder_count, datetime.now(), None)
                    db.add_history(user_id, "reminded", "Scheduled reminder re-sent to group")
                else:
                    db.create_reminder(queue_id, user_id, username, None)
                    db.add_history(user_id, "reminded", "Initial reminder sent to group")
                logger.info(f"Sent reminder to @{username} in group {self.group_chat_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to group: {e}")
        else:
            # Fallback to DM if no group set
            name = first_name or username or f"User {user_id}"
            message = (
                f"Hello {name}! 🔔\n\n"
                "It's your turn for paper review!\n\n"
                "Please use /skip to pass to the next person."
            )

            try:
                await self.application.bot.send_message(chat_id=user_id, text=message)
                if active_reminder:
                    reminder_id, reminder_count, last_reminded_at, next_reminder_at = active_reminder
                    db.update_reminder(reminder_id, reminder_count, datetime.now(), None)
                    db.add_history(user_id, "reminded", "Scheduled reminder re-sent via DM")
                else:
                    db.create_reminder(queue_id, user_id, username, None)
                    db.add_history(user_id, "reminded", "Initial reminder sent via DM")
                logger.info(f"Sent reminder to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send reminder to user {user_id}: {e}")

    async def handle_autopop(self):
        """Auto-pop users with active reminders"""
        reminders = db.get_active_reminders()
        if not reminders:
            return

        for reminder_id, queue_id, user_id, username, reminder_count in reminders:
            resolved_queue_id = queue_id or db.find_queue_id(user_id, username)
            if resolved_queue_id is None:
                logger.warning(f"Auto-pop: could not resolve queue entry for reminder {reminder_id}")
                db.delete_reminder(reminder_id)
                continue

            db.move_user_to_back_by_queue_id(resolved_queue_id)
            db.delete_reminder(reminder_id)
            db.add_history(user_id or 0, "auto_popped", "Moved to back after auto-pop schedule")
            logger.info(f"Auto-popped queue_id={resolved_queue_id} (reminder_id={reminder_id})")

    def setup_scheduler(self, minute: int, hour: int, day_of_week: int,
                        autopop_minute: int, autopop_hour: int, autopop_day_of_week: int):
        """Setup the scheduler for weekly reminders"""
        # Weekly reminder job
        self.scheduler.add_job(
            self.send_weekly_reminder,
            trigger=CronTrigger(
                minute=minute,
                hour=hour,
                day_of_week=day_of_week,
                timezone=self.timezone
            ),
            id='weekly_reminder',
            name='Weekly Reminder',
            replace_existing=True
        )

        # Auto-pop job
        self.scheduler.add_job(
            self.handle_autopop,
            trigger=CronTrigger(
                minute=autopop_minute,
                hour=autopop_hour,
                day_of_week=autopop_day_of_week,
                timezone=self.timezone
            ),
            id='autopop_reminder',
            name='Auto-Pop Reminder',
            replace_existing=True
        )

        logger.info(f"Scheduler configured: Weekly reminder on day {day_of_week} at {hour:02d}:{minute:02d}")
        logger.info(f"Scheduler configured: Auto-pop on day {autopop_day_of_week} at {autopop_hour:02d}:{autopop_minute:02d}")

    async def post_init(self, application: Application):
        """Post initialization hook"""
        self.application = application
        self.group_chat_id = db.get_group_chat_id()
        if self.group_chat_id:
            logger.info(f"Loaded group chat ID: {self.group_chat_id}")
        self.scheduler.start()
        logger.info("Scheduler started")

    def run(self, minute: int = 0, hour: int = 9, day_of_week: int = 1,
            autopop_minute: int = 0, autopop_hour: int = 18, autopop_day_of_week: int = 0):
        """Run the bot"""
        # Build application
        self.application = Application.builder().token(self.token).post_init(self.post_init).build()

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("queue", self.queue_command))
        self.application.add_handler(CommandHandler("skip", self.skip_command))

        # Admin commands
        self.application.add_handler(CommandHandler("setgroup", self.setgroup_command))
        self.application.add_handler(CommandHandler("adduser", self.adduser_command))
        self.application.add_handler(CommandHandler("removeuser", self.removeuser_command))
        self.application.add_handler(CommandHandler("initqueue", self.initqueue_command))
        self.application.add_handler(CommandHandler("clearqueue", self.clearqueue_command))
        self.application.add_handler(CommandHandler("noreview", self.noreview_command))
        self.application.add_handler(CommandHandler("setschedule", self.setschedule_command))
        self.application.add_handler(CommandHandler("nextreminder", self.nextreminder_command))
        self.application.add_handler(CommandHandler("setautopop", self.setautopop_command))

        # Setup scheduler
        self.setup_scheduler(minute, hour, day_of_week, autopop_minute, autopop_hour, autopop_day_of_week)

        # Start the bot
        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """Main function"""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return

    # Get schedule configuration (DB overrides .env if set)
    schedule = db.get_schedule()
    if schedule:
        day_of_week, hour, minute = schedule
    else:
        minute = int(os.getenv("REMINDER_SCHEDULE_MINUTE", "0"))
        hour = int(os.getenv("REMINDER_SCHEDULE_HOUR", "9"))
        day_of_week = int(os.getenv("REMINDER_SCHEDULE_DAY_OF_WEEK", "1"))

    # Get auto-pop schedule configuration (DB overrides .env if set)
    autopop_schedule = db.get_autopop_schedule()
    if autopop_schedule:
        autopop_day_of_week, autopop_hour, autopop_minute = autopop_schedule
    else:
        autopop_minute = int(os.getenv("AUTOPOP_SCHEDULE_MINUTE", "0"))
        autopop_hour = int(os.getenv("AUTOPOP_SCHEDULE_HOUR", "18"))
        autopop_day_of_week = int(os.getenv("AUTOPOP_SCHEDULE_DAY_OF_WEEK", "0"))
    timezone = os.getenv("TIMEZONE", "UTC")

    # Get admin IDs (comma-separated list)
    admin_ids_str = os.getenv("ADMIN_USER_IDS", "")
    admin_ids = []
    if admin_ids_str:
        try:
            admin_ids = [int(uid.strip()) for uid in admin_ids_str.split(",") if uid.strip()]
        except ValueError:
            logger.warning("Invalid ADMIN_USER_IDS format. Expected comma-separated integers.")

    # Create and run bot
    bot = ReminderBot(token, timezone, admin_ids)
    bot.run(minute, hour, day_of_week, autopop_minute, autopop_hour, autopop_day_of_week)


if __name__ == "__main__":
    main()
