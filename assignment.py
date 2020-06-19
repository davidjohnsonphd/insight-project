#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# For data management
import numpy as np
import pandas as pd

# Other utilities
import datetime as dt # For datetime
import psycopg2 # For querying databases

# Create a dictionary with group names and their size in proportion to each 
# other. This is the 'interactive' portion of the script.
groups = pd.DataFrame({
    'Control': .20, 'Generic': .40, 'Personalized': .40
    }.items(), columns=['group', 'size'])

# Function to execute SQL queries
def execute_query(query, connection, args=None):
    con = connection
    cur = con.cursor()
    if args:
        cur.execute(query, args)
    else:
        cur.execute(query)

    results = cur.fetchall()
    cur.close()
    con.close()
    return results

# Get data on finished applications from greenhouse server
greenhouse = open('credentials_greenhouse.txt').readlines()
connection = psycopg2.connect(database=greenhouse[0].strip(),
                           user=greenhouse[1].strip(),
                           password=greenhouse[2].strip(),
                           host=greenhouse[3].strip(),
                           port=greenhouse[4].strip())

# Extract relevant columns
all_completed = execute_query(query = """
SELECT hashed_email_address, year, session, application_submission_date 
FROM completed_apps;
""", connection = connection)

# Convert to a pandas DataFrame
all_completed = pd.DataFrame(all_completed,
                             columns=[
                                 'hashed_email_address', 'year', 'session',
                                 'application_submission_date'
                             ])

# Get data on unfinished applications from heroku server
heroku = open('credentials_heroku.txt').readlines()
connection = psycopg2.connect(database=heroku[0].strip(),
                           user=heroku[1].strip(),
                           password=heroku[2].strip(),
                           host=heroku[3].strip(),
                           port=heroku[4].strip())

# Extract relevant columns
all_apps = execute_query("""
SELECT hashed_email_address, program, created_at, updated_at, ai_motivation, 
       ai_tools, coursework, dc_education, dc_innovation,
       dc_motivation, de_motivation, debugging, dev_ops_motivation,
       ds_motivation, largest_codebase, largest_team,
       ml_innovation, ml_problem, networking, sec_motivation,
       sec_tradeoffs, side_projects, statistical_methods,
       technical_tradeoffs, tools
FROM consulting_heroku_export;
""", connection = connection)

# Convert to a pandas DataFrame
all_apps = pd.DataFrame(
    all_apps,
    columns=[
        'hashed_email_address', 'program', 'created_at', 'updated_at',
        'ai_motivation', 'ai_tools', 'coursework', 'dc_education',
        'dc_innovation', 'dc_motivation', 'de_motivation', 'debugging',
        'dev_ops_motivation', 'ds_motivation', 'largest_codebase',
        'largest_team', 'ml_innovation', 'ml_problem', 'networking',
        'sec_motivation', 'sec_tradeoffs', 'side_projects',
        'statistical_methods', 'technical_tradeoffs', 'tools'
    ])

# Replace empty strings with NaN
all_apps.replace("", np.nan, inplace = True)


# Do some basic cleaning; delete accounts before 4/19/19 at 7:30 (testing)
start_date = pd.to_datetime('2019-04-19 07:30:00.0')
all_apps = all_apps[all_apps['created_at'] > start_date]

# Remove applications with gibberish responses
writing_questions = [
    'ai_motivation', 'ai_tools', 'coursework', 'dc_education', 'dc_innovation',
    'dc_motivation', 'de_motivation', 'debugging', 'dev_ops_motivation',
    'ds_motivation', 'largest_codebase', 'largest_team', 'ml_innovation',
    'ml_problem', 'networking', 'sec_motivation', 'sec_tradeoffs',
    'side_projects', 'statistical_methods', 'technical_tradeoffs', 'tools'
]

gibberish = all_apps[writing_questions].copy()  # Extract all question data

# Loop to indicate whether each response had one space
for i in range(gibberish.columns.size):
    gibberish.iloc[:, i] = gibberish.iloc[:, i].str.contains(' ') == False

# Use cutoff of five responses without spaces
keep_applications = gibberish.sum(axis=1, skipna=True) < 5

# Remove data without any spaces in 5 or more columns, as gibberish responses
# typically don't have any spaces
all_apps = all_apps[keep_applications]

#Subset only relevant columns
all_apps = all_apps[['hashed_email_address', 'program', 'updated_at']]

# Change data to datetype format in completed app dataset
all_completed['application_submission_date'] = pd.to_datetime(
    all_completed['application_submission_date'],
    infer_datetime_format=True).dt.tz_localize(None)

# Drop duplicates from completed file
all_completed.sort_values(by='application_submission_date',
                          ascending=False,
                          inplace=True)
all_completed.drop_duplicates('hashed_email_address', inplace=True)

# Create a feature indicating cohort
all_completed['cohort'] = all_completed['year'].astype(str).str.cat(
    all_completed['session'])

#Merge all and completed applications
df = all_apps.merge(all_completed, how = 'left', on = 'hashed_email_address')

# Identify applicants to A/B test
# Calculate days since an application was last completed
df['days_since_updated'] = (pd.to_datetime('today') - df['updated_at']).dt.days

# Create a boolean indicating whether an app has been updated in last 6 months
df['updated_recent'] = df['days_since_updated'] < (365 / 2)

# Create a variable indicating current session
current_session = df['cohort'].sort_values(ascending = False).iloc[0]

# Create a boolean indicating if an app was submitted in the current session
df['current_submission'] = df['cohort'] == current_session

# Create a boolean indicating who has information about their program
df['has_program'] = df['program'].notna() 

# Create a boolean indicating who to nudge
# Based on activity in past six months, no current submission, program info
df['to_nudge'] = df['updated_recent'] & (
    df['current_submission'] == False) & df['has_program']

# Create a string with today's date to track campaign
todays_date = 'campaign_' + pd.to_datetime('today').strftime("%m/%d/%Y")

# Divide groups (see top of script) so that their totals sum to 100 
# (if user inputs precentages or whole numbers)
groups['size'] = groups['size'] / groups['size'].sum()

# Create an empty column to add in random assignment
df[todays_date] = np.nan

# Populate column with random assignment
df.loc[df['to_nudge'], todays_date] = np.random.choice(groups['group'],
                                                      df['to_nudge'].sum(),
                                                      p=groups['size'])

# Create a csv file with emails randomly assigned to campaigns
email_list = df.loc[df[todays_date].notna(
), ['hashed_email_address', todays_date]]
email_list.sort_values(todays_date, inplace=True)
email_list.to_csv('email_list_' +
                  pd.to_datetime('today').strftime("%m-%d-%Y") + '.csv',
                  index=False)
