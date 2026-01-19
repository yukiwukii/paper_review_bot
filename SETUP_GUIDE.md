# Quick Setup Guide

This guide will help you set up your Telegram reminder bot for group chat usage.

## Step 1: Create Your Bot

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` to create a new bot
3. Follow the prompts to name your bot
4. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

## Step 2: Get Your User ID (Optional)

If you want to be an admin besides the group admins:

1. Search for [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send any message to it
3. Copy your user ID (it's a number like `123456789`)

## Step 3: Configure the Bot

1. Open the `.env` file in the project directory
2. Add your bot token:
   ```
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
3. (Optional) Add admin user IDs:
   ```
   ADMIN_USER_IDS=123456789,987654321
   ```
4. Configure the reminder schedule:
   ```
   REMINDER_SCHEDULE_MINUTE=0
   REMINDER_SCHEDULE_HOUR=9
   REMINDER_SCHEDULE_DAY_OF_WEEK=0  # 0=Monday, 6=Sunday
   TIMEZONE=UTC
   ```

## Step 4: Add Bot to Your Group

1. Create a group chat (or use an existing one)
2. Add your bot to the group
   - Click on group name → Add Members → Search for your bot
3. (Recommended) Make the bot an admin
   - Click on group name → Administrators → Add Administrator
   - Select your bot
   - Grant "Send Messages" permission (minimum)

## Step 5: Start the Bot

Run the bot:
```bash
python bot.py
```

You should see:
```
INFO - Database initialized successfully
INFO - Scheduler started
INFO - Starting bot...
```

## Step 6: Initialize in Group Chat

In your group chat:

1. Set the group as reminder target:
   ```
   /setgroup
   ```

2. Initialize the queue with your team members:
   ```
   /initqueue @alice @bob @charlie @david
   ```

3. Check the queue:
   ```
   /queue
   ```

## Step 7: Test It Out

You can manually trigger a reminder or wait for the scheduled time. To test immediately:

1. Update `.env` to trigger in a few minutes:
   ```
   REMINDER_SCHEDULE_MINUTE=25  # If it's currently 9:23, set to 25
   REMINDER_SCHEDULE_HOUR=9     # Current hour
   REMINDER_SCHEDULE_DAY_OF_WEEK=*  # Any day (for testing)
   ```

2. Restart the bot

3. Wait for the reminder to trigger

## Common Issues

### Bot doesn't respond to commands
- Make sure the bot is added to the group
- Check that the bot has permission to send messages
- Verify the bot is running (`python bot.py`)

### Can't use admin commands
- Make sure you're a group admin, OR
- Add your user ID to `ADMIN_USER_IDS` in `.env`

### Reminders not sending
- Verify you ran `/setgroup` in the group chat
- Check the scheduler configuration in `.env`
- Look at the logs for errors

### Users not getting @mentioned
- Make sure users have usernames set in Telegram
- Use the exact username when adding to queue

## Daily Usage

### Add a new person to the queue
```
/adduser @newperson
```

### Remove someone from the queue
```
/removeuser @someone
```

### Reorder the entire queue
```
/initqueue @person1 @person2 @person3
```

### View current queue
```
/queue
```

### When reminded
- Acknowledge: `/ack`
- Skip your turn: `/skip`

## Advanced Configuration

### Multiple Reminder Times

To have reminders on multiple days, you'll need to modify the code or run multiple instances.

### Custom Reminder Messages

Edit the message templates in [bot.py](bot.py):
- Line ~367: Initial reminder message
- Line ~450: Retry reminder message

### Change Retry Count

Edit [bot.py](bot.py) line ~401:
```python
if reminder_count >= 3:  # Change 3 to your desired count
```

## Getting Help

If you encounter issues:
1. Check the logs when running `python bot.py`
2. Verify your `.env` configuration
3. Make sure all dependencies are installed: `pip install -r requirements.txt`
4. Check the [README.md](README.md) for more details
