import os
import sys
import time
import logging
import smtplib, ssl
import connect_to_database
import pandas as pd
import gsheet
from datetime import date, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from functools import reduce
from dotenv import load_dotenv
from emailing import log_and_email
from overwrite_arcgis_csvs import update_all_csvs
import parse_filings
import parse_settings
import persist

load_dotenv()
local_dev = os.getenv("LOCAL_DEV") == "true"

logger = logging.getLogger()
logging.basicConfig(stream=sys.stdout)
logger.setLevel(logging.INFO)


# returns date, mm_dd_yyyy format, where _ is determined by sep, number_of_days days ago or from today's date, depending on past_or_future
def get_date_from_today(sep, number_of_days, past_or_future):
    today = date.today()

    if past_or_future == "future":
        return_date = today + timedelta(days=number_of_days)
    else:
        return_date = today - timedelta(days=number_of_days)

    return return_date.strftime(f"%-m{sep}%-d{sep}%Y")

def perform_task_and_catch_errors(task_function, task_name, error=False):
    before = time.time()
    logger.info(f"\n{task_name}...")
    for tries in range(1, 6):
        try:
            task_function()
            logger.info(f"Finished {task_name} in {round(time.time() - before, 2)} seconds.")
            return
        except Exception as error:
            logger.error(f"Unanticipated Error {task_name} on attempt {tries} of 5:\n{str(error)}")
    log_and_email(f"{task_name} failed on every attempt. Check Heroku logs for more details.", f"{task_name} failed", error=True)

def scrape_filings():
    seven_days_ago = get_date_from_today("-", 7, "past")
    parse_filings.parse_filings_on_cloud(seven_days_ago, date.today().strftime(f"%-m-%-d-%Y"))

def scrape_settings():
    ninety_days_later = get_date_from_today("-", 90, "future")
    seven_days_ago = get_date_from_today("-", 7, "past")
    parse_settings.parse_settings_on_cloud(seven_days_ago, ninety_days_later)

def update_first_court_apperance():
    persist.update_first_court_apperance_column()


def scrape_filings_and_settings_task():
    perform_task_and_catch_errors(scrape_filings, "Scraping filings")
    perform_task_and_catch_errors(scrape_settings, "Scraping settings")
    perform_task_and_catch_errors(update_first_court_apperance, "Updating first_court_appearance column")
    perform_task_and_catch_errors(update_all_csvs, "Updating arcGIS csvs")

    cols = "case_number, status, precinct, style, plaintiff, defendants, plaintiff_zip, defendant_zip, case_type, date_filed, active_or_inactive, judgment_after_moratorium, CAST(first_court_appearance AS text), type, date, amount, awarded_to, awarded_against, judgement_for, match_score, attorneys_for_plaintiffs, attorneys_for_defendants, comments"
    gsheet.dump_to_sheets('Court_scraper_filings_archive','filings_archive',"SELECT "+ cols + " FROM filings_archive")
    gsheet.dump_to_sheets('Court_scraper_filings_archive','events',"SELECT * FROM event")
    gsheet.dump_to_sheets('Court_scraper_settings_archive','settings_archive',"SELECT * FROM setting")
    gsheet.dump_to_sheets('Court_scraper_evictions_archive','evictions_archive',"SELECT "+ cols +" FROM filings_archive WHERE case_type='Eviction'") #Convert Date to Text
    gsheet.dump_to_sheets('Court_scraper_evictions_archive','events',"SELECT * FROM eviction_events")

# scrape filings and settings every Monday at 3:00 A.M. EST
if __name__ == "__main__":
    sched = BlockingScheduler()
    sched.add_job(scrape_filings_and_settings_task, 'interval', days=1, start_date='2020-11-11 3:00:00', timezone='US/Eastern')
    sched.start()
