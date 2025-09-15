# NOOB-2-ROOT Discord Bot

A feature-rich Discord bot for gamified learning, quizzes, community engagement, and productivity.

## Features

- **AI-Powered Quizzes:**
  - `/quiz` command generates unique multiple-choice questions using OpenRouter AI.
  - Supports batch quizzes, difficulty selection, and streak rewards.
  - Challenge up to 5 friends in group quiz duels with `/challenge_friend`.
  - Fallback to stored questions if AI is rate-limited (configurable).

- **AI Tutor:**
  - `/tutor` command lets users ask for explanations or step-by-step solutions using AI.

- **Progress Tracking:**
  - `/progress` shows points, streaks, category points, and roles for any user.
  - `/leaderboard` displays top users by points.

- **Resource & Project Sharing:**
  - `/resource` and `/resource_add` for sharing and discovering learning resources.
  - `/submit_project` for project showcase and upvoting.

- **To-Do & Reminders:**
  - `/todo_add`, `/todo_list`, `/todo_update`, `/todo_complete` for personal task management.
  - `/remind` and `/remind_user` for reminders.

- **Onboarding & Roles:**
  - New users receive a welcome message and are prompted to introduce themselves.
  - Posting in the introductions channel grants the "Full Access" role automatically.

- **Moderation Tools:**
  - Commands for kicking, banning, muting, and clearing tasks (mod only).

## Setup

1. **Clone the repository:**
   ```
   git clone <your-repo-url>
   ```
2. **Install dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Configure environment variables:**
   - Create a `.env` file with your Discord bot token and OpenRouter API key:
     ```
     DISCORD_TOKEN=your_discord_token
     OPENROUTER_API_KEY=your_openrouter_api_key
     ```
4. **Run the bot:**
   ```
   python app.py
   ```

## Customization
- Edit `app.py` to adjust categories, roles, channel IDs, and feature toggles.
- Add or edit questions in `quizzes.json` for fallback quiz content.

## Contributing
Pull requests and suggestions are welcome! See the code for modular command structure and add your own features.

## License
MIT

---

**Contact:** For help or feature requests, open an issue or reach out to me via hi@theodorio.cv 
