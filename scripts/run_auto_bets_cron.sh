#!/bin/bash
# Auto-betting cron wrapper
# Garantiza DJANGO_SETTINGS_MODULE=betting_bot.settings sin importar /etc/environment
# Fix 2: el cron estaba heredando config.settings.production de /etc/environment
set -euo pipefail

export DJANGO_SETTINGS_MODULE=betting_bot.settings
cd /var/www/predicta.com.co

exec /var/www/predicta.com.co/venv/bin/python manage.py run_auto_bets >> /var/www/predicta.com.co/logs/auto_betting.log 2>&1
