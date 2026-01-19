# Changes Made for Group Chat & Manual Queue Management

## Overview
The bot has been updated from a self-service queue system to a group chat reminder system with manual admin-controlled queue management.

## Major Changes

### 1. Group Chat Integration
- Bot now sends reminders to a designated group chat instead of DMs
- Added `/setgroup` command to set the target group chat
- Reminders use @username mentions in the group
- Supports both group messages and DM fallback

### 2. Manual Queue Management
- Removed `/join` and `/leave` commands (users can't add themselves)
- Added `/adduser @username` - admins add users by username
- Added `/removeuser @username` - admins remove users by username
- Added `/initqueue @user1 @user2 @user3` - initialize entire queue at once
- Added `/clearqueue` - clear the entire queue

### 3. Admin Authorization System
- Added support for admin user IDs via environment variable `ADMIN_USER_IDS`
- Group admins automatically have admin permissions
- Admin commands are restricted to authorized users only
- `/start` and `/help` show different content for admins vs regular users

### 4. Database Enhancements
- Modified `add_user_to_queue()` to check for duplicate usernames
- Added `clear_queue()` method to clear all queue entries
- Queue now supports username-based storage (user_id can be 0 for manual additions)

### 5. Reminder Logic Updates
- `send_weekly_reminder()` now sends to group chat with @mentions
- `handle_reminder_retry()` updated to support group chat notifications
- All reminder messages adapted for group context
- Retry notifications sent to group instead of DM

### 6. Configuration Updates
- Added `ADMIN_USER_IDS` environment variable
- Updated `.env.example` with admin configuration
- Improved documentation for day-of-week settings

## New Commands

### Admin Commands
- `/setgroup` - Set current group as reminder target
- `/adduser @username` - Add user to queue
- `/removeuser @username` - Remove user from queue
- `/initqueue @user1 @user2 @user3` - Initialize queue
- `/clearqueue` - Clear entire queue

### Removed Commands
- `/join` - No longer needed (admins add users)
- `/leave` - No longer needed (admins remove users)

### Unchanged Commands
- `/start` - Welcome message (now shows admin commands if authorized)
- `/help` - Help information (now shows admin commands if authorized)
- `/queue` - View current queue
- `/ack` - Acknowledge reminder
- `/skip` - Skip turn

## Files Modified

1. **bot.py**
   - Added admin authorization methods
   - Added group chat support
   - Added new admin commands
   - Updated reminder methods for group chat
   - Updated command handlers

2. **database.py**
   - Added `clear_queue()` method
   - Updated `add_user_to_queue()` to check usernames
   - Enhanced logging

3. **.env.example**
   - Added `ADMIN_USER_IDS` configuration
   - Improved documentation

4. **README.md**
   - Complete rewrite for group chat usage
   - Updated workflow examples
   - Added admin command documentation
   - Updated setup instructions

## Files Added

1. **SETUP_GUIDE.md** - Step-by-step setup guide
2. **CHANGES.md** - This file

## Workflow Changes

### Before (Self-Service)
1. Users send `/join` to add themselves
2. Bot sends DM to next person
3. User responds with `/ack` or `/skip`

### After (Admin-Managed Group Chat)
1. Admin uses `/initqueue @user1 @user2 @user3`
2. Bot sends reminder to group with @mention
3. Mentioned user responds in group with `/ack` or `/skip`

## Migration Notes

If you have an existing database from the old version:
- The queue will still work, but users were added with actual user IDs
- You can `/clearqueue` and `/initqueue` to start fresh with usernames
- Old reminders will continue to work via DM fallback

## Testing Recommendations

1. Add bot to a test group
2. Make yourself a group admin or add your ID to `ADMIN_USER_IDS`
3. Use `/setgroup` in the group
4. Use `/initqueue @yourself @another_user` to test
5. Set a reminder schedule for a few minutes away to test
6. Verify @mentions work in group
7. Test `/ack` and `/skip` commands
8. Test retry logic (wait 24h or modify code for faster testing)
