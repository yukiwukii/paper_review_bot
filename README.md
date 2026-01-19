# Telegram Reminder Bot

A Telegram bot that manages a queue of users and sends weekly reminders to a group chat.

## Features

- **Group Chat Integration**: Bot sends reminders to a designated group chat with @mentions
- **Manual Queue Management**: Admins manually add/remove users by username
- **Initialize Queue**: Set the entire queue order at once with a single command
- **Weekly Automated Reminders**: Reminds the next person in queue at scheduled intervals
- **Skip Functionality**: Users can use `/skip` to pass to the next person
- **Auto-Pop Schedule**: Moves the current user to the back at a set time if they didn't act
- **Admin Authorization**: Group admins and configured admin users can manage the queue
- **SQLite Database**: Persistent storage for queue and reminder history
- **Configurable Schedule**: Set reminder time via environment variables
- **Timezone Support**: Configure your preferred timezone

## Requirements

- Python 3.8+
- A Telegram Bot Token (get one from [@BotFather](https://t.me/botfather))

## Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. Edit the `.env` file and configure:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
ADMIN_USER_IDS=your_telegram_user_id
REMINDER_SCHEDULE_MINUTE=0
REMINDER_SCHEDULE_HOUR=9
REMINDER_SCHEDULE_DAY_OF_WEEK=0
TIMEZONE=UTC
AUTOPOP_SCHEDULE_MINUTE=0
AUTOPOP_SCHEDULE_HOUR=18
AUTOPOP_SCHEDULE_DAY_OF_WEEK=0
```

### Configuration Details

- `TELEGRAM_BOT_TOKEN`: Your bot token from @BotFather
- `ADMIN_USER_IDS`: Comma-separated list of Telegram user IDs who can manage the queue (get yours from @userinfobot)
- `REMINDER_SCHEDULE_MINUTE`: Minute of the hour (0-59)
- `REMINDER_SCHEDULE_HOUR`: Hour of the day in 24-hour format (0-23)
- `REMINDER_SCHEDULE_DAY_OF_WEEK`: Day of week (0=Monday, 1=Tuesday, ..., 6=Sunday)
- `TIMEZONE`: Timezone for scheduling (e.g., "UTC", "America/New_York", "Europe/London", "Asia/Tokyo")
- `AUTOPOP_SCHEDULE_MINUTE`: Minute of the hour for auto-pop (0-59)
- `AUTOPOP_SCHEDULE_HOUR`: Hour of the day for auto-pop (0-23)
- `AUTOPOP_SCHEDULE_DAY_OF_WEEK`: Day of week for auto-pop (0=Monday, 1=Tuesday, ..., 6=Sunday)

Example: To send reminders every Monday at 9:00 AM UTC with two admins:
```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
ADMIN_USER_IDS=123456789,987654321
REMINDER_SCHEDULE_MINUTE=0
REMINDER_SCHEDULE_HOUR=9
REMINDER_SCHEDULE_DAY_OF_WEEK=0
TIMEZONE=UTC
```

## Usage

### Starting the Bot

Run the bot with:
```bash
python bot.py
```

The bot will start and begin polling for messages. Keep this running to maintain the bot's functionality.

### Setup Steps

1. Create your bot with @BotFather on Telegram
2. Add the bot to your group chat
3. Make the bot an admin in the group (or ensure it can send messages)
4. Start the bot with `python bot.py`
5. In the group chat, use `/setgroup` to designate it as the reminder target
6. Initialize the queue with `/initqueue @user1 @user2 @user3`

### Bot Commands

**User Commands:**
- `/start` - Welcome message and command list
- `/help` - Show help information
- `/queue` - View the current queue
- `/skip` - Skip your turn and pass to the next person

**Admin Commands** (only for configured admins and group admins):
- `/setgroup` - Set the current group as the reminder target
- `/adduser @username` - Add a user to the queue by their username
- `/removeuser @username` - Remove a user from the queue
- `/initqueue @user1 @user2 @user3` - Initialize/replace the entire queue
- `/clearqueue` - Clear the entire queue
- `/setschedule <day> <hour> <minute>` - Set reminder schedule
- `/setautopop <day> <hour> <minute>` - Set auto-pop schedule
- `/noreview` - Skip this week's reminder (queue order unchanged)

### How It Works

1. Admins add users to the queue using `/initqueue @user1 @user2 @user3` or `/adduser @username`
2. Every week (based on your configuration), the bot reminds the first person in the group chat with an @mention
3. The reminded user can:
   - Use `/skip` to pass their turn - they'll be moved to the back and the next person is reminded immediately
   - Do nothing - they'll be moved to the back at the auto-pop schedule

### Example Workflow

```
[In the group chat]
Admin: /setgroup
Bot: Group chat set! Reminders will be sent to this group.

Admin: /initqueue @alice @bob @charlie
Bot: Queue initialized with 3 users:
     1. @alice
     2. @bob
     3. @charlie

[Weekly reminder triggers - Monday 9 AM]
Bot: @alice 🔔

     This is your reminder!

     Please use /skip to pass to the next person.

[Next week]
Bot: @bob 🔔

     This is your reminder!
```

## Database

The bot uses SQLite to store:
- User queue with positions
- Active reminders for the current user
- Reminder history for tracking

Database file: `reminder_bot.db` (created automatically)

## File Structure

```
.
├── bot.py              # Main bot logic and command handlers
├── database.py         # Database operations and schema
├── requirements.txt    # Python dependencies
├── .env               # Configuration (create from .env.example)
├── .env.example       # Example configuration
├── .gitignore         # Git ignore file
└── README.md          # This file
```

## Development

### Running in Development

For development, you might want to test reminders more frequently. Modify the cron schedule in `.env`:

```
# Test every 5 minutes (not recommended for production)
REMINDER_SCHEDULE_MINUTE=*/5
REMINDER_SCHEDULE_HOUR=*
REMINDER_SCHEDULE_DAY_OF_WEEK=*
```

### Database Schema

**user_queue**
- `id`: Primary key
- `user_id`: Telegram user ID (unique)
- `username`: Telegram username
- `first_name`: User's first name
- `last_name`: User's last name
- `position`: Position in queue
- `added_at`: Timestamp when added

**active_reminders**
- `id`: Primary key
- `user_id`: Telegram user ID
- `reminder_count`: Number of reminders sent (0-3)
- `created_at`: When reminder was created
- `last_reminded_at`: Last reminder timestamp
- `next_reminder_at`: When to send next reminder

**reminder_history**
- `id`: Primary key
- `user_id`: Telegram user ID
- `action`: Action performed (joined, left, reminded, skipped, auto_popped)
- `timestamp`: When action occurred
- `notes`: Additional notes

## Troubleshooting

### Bot doesn't respond
- Check that the bot is running (`python bot.py`)
- Verify your bot token is correct in `.env`
- Make sure you've started a conversation with the bot (send `/start`)

### Reminders not being sent
- Check the scheduler configuration in `.env`
- Verify the timezone is correct
- Check logs for any errors
- Ensure at least one user is in the queue

### Database errors
- Delete `reminder_bot.db` to reset (you'll lose all data)
- Check file permissions in the directory

## License

MIT License - feel free to use and modify as needed.
