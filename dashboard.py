#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# For analyses
import numpy as np
import pandas as pd
import datetime as dt # For managing datetime objects
import random # For random draws
import re # For regular expressions 

# For dash plots
import dash
import dash_core_components as dcc
import dash_html_components as html
import plotly.graph_objects as go
from dash.dependencies import Input, Output

#For querying and creating databases
from sqlalchemy import create_engine

# Read in postgres credentials
greenhouse = open('credentials_greenhouse.txt').readlines()
database = greenhouse[0].strip()
username = greenhouse[1].strip()
password = greenhouse[2].strip()
host = greenhouse[3].strip()
port = greenhouse[4].strip()

# Create a connection to database using postgreSQL
engine = create_engine('postgresql://%s:%s@%s:%s/%s' %
                       (username, password, host, port, database))

# Query to extract data
sql_query = """
SELECT hashed_email_address, year, session, application_submission_date
FROM completed_apps;
"""

# Extract relevant columns
all_completed = pd.read_sql_query(sql_query, engine)

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

# Create a variable indicating current session
current_session = all_completed['cohort'].sort_values(
    ascending=False).iloc[0]  #Current session

# Choose only data from current sesion
all_completed = all_completed[all_completed['cohort'] == current_session]

# # Read in postgres credentials
# campaign_info = open('credentials_campaign.txt').readlines()
# database = campaign_info[0].strip()
# username = campaign_info[1].strip()
# password = campaign_info[2].strip()

# # Create a connection to database using postgreSQL
# engine = create_engine('postgresql://%s:%s@localhost/%s' %
#                        (username, password, database))

# # Read in the existing SQL database
# # Contains information about any campaigns started
# df_campaign = pd.read_sql_table('campaign_table', con=engine).drop('index',
#                                                                    axis=1)

# # Change none to NaN
# df_campaign.fillna(value = np.nan, inplace = True)

# Read in the campaign data from a csv file
df_campaign = pd.read_csv('simulated_data.csv')

# Merge datasets
df_dash = all_completed.merge(df_campaign, 
                              how = 'outer', 
                              on = 'hashed_email_address')

# Change condition names
df_dash.loc[df_dash['campaign_06/15/2020'] ==
            'C', 'campaign_06/15/2020'] = 'Control'

# Function to generate fake data for demo
start = pd.to_datetime('06/15/2020')
end = pd.to_datetime('today').normalize()


def random_time(start, end):
    """Get a time between the start and end time.
    Both times should be datetime objects.
    """
    random_date = start + (end - start) * random.random()
    return random_date

# Generate the fake data for groups
a_group = df_dash.loc[df_dash['campaign_06/15/2020'] == 'A', ].sample(
    300, random_state=1337).index
df_dash.loc[df_dash.index[a_group],
            'application_submission_date'] = df_dash.iloc[a_group, ].apply(
                lambda x: random_time(start, end), 1)
df_dash.loc[df_dash.index[a_group], 'cohort'] = current_session

b_group = df_dash.loc[df_dash['campaign_06/15/2020'] == 'B', ].sample(
    200, random_state=1337).index
df_dash.loc[df_dash.index[b_group],
            'application_submission_date'] = df_dash.iloc[b_group, ].apply(
                lambda x: random_time(start, end), 1)
df_dash.loc[df_dash.index[b_group], 'cohort'] = current_session

c_group = df_dash.loc[df_dash['campaign_06/15/2020'] == 'Control', ].sample(
    100, random_state=1337).index
df_dash.loc[df_dash.index[c_group],
            'application_submission_date'] = df_dash.iloc[c_group, ].apply(
                lambda x: random_time(start, end), 1)
df_dash.loc[df_dash.index[c_group], 'cohort'] = current_session

# Create a second campaign for looping purposes
df_dash['campaign_06/18/2020'] = df_dash['campaign_06/15/2020']

# Round submission time to the day submitted
df_dash['application_submission_date'] = df_dash[
    'application_submission_date'].dt.floor('d')

# List of all the campaigns
campaign_names = df_dash.filter(regex='campaign', axis=1).columns.tolist()

#Create an empty DataFrame to store data
all_campaigns = pd.DataFrame(
    columns=['Date', 'Condition', 'Counts', 'Campaign', 'Size'])

# Loop to get counts for each campaign
for i in campaign_names:
    # Change all NA values into None
    df_dash[i].fillna(value="None", inplace=True)

    # Group by date and condition and return counts
    counts = df_dash.groupby(
        by=['application_submission_date', i]).size().reset_index()
    counts.columns = ['Date', 'Condition', 'Counts']
    min_date = counts.Date.min()
    max_date = counts.Date.max()
    counts.set_index(['Date', 'Condition'], inplace=True)

    # Use indexing to fill in missing data
    application_range = pd.date_range(min_date, max_date)
    conditions = pd.Series(df_dash[i].unique()).sort_values()
    new_index = pd.MultiIndex.from_product([application_range, conditions],
                                           names=['Date', 'Condition'])
    counts = counts.reindex(new_index).reset_index()

    #Replace missing data with 0
    counts.fillna(value=0, inplace=True)

    # Add in an indicator for campaign
    campaign_date = re.search('campaign_(.*)', i).group(1)
    counts['Campaign'] = campaign_date

    # Create a dictionary with sample size
    condition_dictionary = df_dash[i].value_counts().to_dict()

    # Create a column indicating size
    counts['Size'] = counts['Condition'].map(condition_dictionary)

    # Concatenate with other campaigns
    all_campaigns = pd.concat([all_campaigns, counts])

# Store all simulated data in a DataFrame    
df = all_campaigns

# Just to make the campaigns have different values
df.loc[(df['Campaign'] == '06/18/2020') &
       (df['Date'] > '06/14/2020'), 'Counts'] = df.loc[
           (df['Campaign'] == '06/18/2020') &
           (df['Date'] > '06/14/2020'), 'Counts'] + 10

# Unique campaign dates
campaigns = df['Campaign'].unique()
           
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

app = dash.Dash(__name__, external_stylesheets=external_stylesheets)

server = app.server

campaigns = df['Campaign'].unique()

# Produces the figure, table, text, and buttons
app.layout = html.Div([
    html.Div(
        [html.Label("Please choose a campaign:")],
        style={
            'width': '100%',
            'display': 'flex',
            'align-items': 'center',
            'justify-content': 'center'
        }),
    html.Div([
        dcc.Dropdown(id='campaign-dropdown',
                     options=[{
                         'label': i,
                         'value': i
                     } for i in campaigns],
                     value=df['Campaign'].unique()[0])
    ],
             style={'width': '100%'}),
    html.Div([dcc.Graph(id='example-graph')]),
    html.Div(
        [html.Label("Please pick a span of dates:")],
        style={
            'width': '100%',
            'display': 'flex',
            'align-items': 'center',
            'justify-content': 'center'
        }),
    html.Div(
        [
            dcc.DatePickerRange(
                id='date-picker-range',
                start_date=pd.to_datetime(df['Campaign'].unique()[0]) -
                dt.timedelta(days=3),
                end_date=max_date)
        ],
        style={
            'width': '100%',
            'display': 'flex',
            'align-items': 'center',
            'justify-content': 'center',
            'padding': '10px 0px 10px 0px'
        }),
    html.Div(
        [
            html.Label(
                "Lift is calculated over the time period specified above.")
        ],
        style={
            'width': '100%',
            'display': 'flex',
            'align-items': 'center',
            'justify-content': 'center'
        }),
    html.Div(id='text-summary',
             style={
                 'width': '100%',
                 'display': 'flex',
                 'align-items': 'center',
                 'justify-content': 'center'
             }),
    html.Div(
        [
            dcc.RadioItems(id='radio-item',
                           options=[
                               {
                                   'label': 'Raw Counts',
                                   'value': 'counts'
                               },
                               {
                                   'label': 'Adjusted Counts',
                                   'value': 'adjusted'
                               },
                           ],
                           value='counts',
                           labelStyle={'display': 'inline-block'})
        ],
        style={
            'width': '100%',
            'display': 'flex',
            'align-items': 'center',
            'justify-content': 'center',
            'padding': '10px 0px 20px 0px'
        }),
])


# Updates the figure
@app.callback(Output(
    component_id='example-graph', component_property='figure'), [
        Input(component_id='date-picker-range',
              component_property='start_date'),
        Input(component_id='date-picker-range', component_property='end_date'),
        Input(component_id='radio-item', component_property='value'),
        Input(component_id='campaign-dropdown', component_property='value')
    ])
def update_output_figure(start_date, end_date, value_counts, value_campaign):
    df_campaign = df[df['Campaign'] == value_campaign].copy()
    df_date = df_campaign[(df_campaign['Date'] >= start_date)
                          & (df_campaign['Date'] <= end_date)].copy()
    study_size = df_date.loc[df_date['Condition'] != 'None', 'Size'].unique(
    ).sum()
    data_list = []
    if value_counts == 'counts':
        for i in conditions:
            if (i != 'None'):
                df_subset = df_date[df_date['Condition'] == i].copy()
                data_list.append(
                    go.Scatter(x=df_subset['Date'],
                               y=df_subset['Counts'],
                               name=i))
        return {
            'data':
            data_list,
            "layout":
            go.Layout(  #title = {"text": "Submissions Per Day"}, 
                yaxis={"title": "Number of Submissions"},
                legend={
                    "x": 0.05,
                    "y": 1.1
                })
        }
    if value_counts == 'adjusted':
        for i in conditions:
            if (i != 'None'):
                df_subset = df_date[df_date['Condition'] == i].copy()
                data_list.append(
                    go.Scatter(
                        x=df_subset['Date'],
                        y=(df_subset['Counts'] /
                           (df_subset['Size'].mean() / study_size)).round(),
                        name=i))
        return {
            'data':
            data_list,
            "layout":
            go.Layout(  #title = {"text": "Submissions Per Day"}, 
                yaxis={"title": "Number of Submissions"},
                legend={
                    "x": 0.05,
                    "y": 1.1
                })
        }


# Updates the text summary
@app.callback(
    Output(component_id='text-summary', component_property='children'), [
        Input(component_id='date-picker-range',
              component_property='start_date'),
        Input(component_id='date-picker-range', component_property='end_date'),
        Input(component_id='campaign-dropdown', component_property='value')
    ])
def update_output_text(start_date, end_date, value_campaign):
    df_campaign = df[df['Campaign'] == value_campaign].copy()
    df_date = df_campaign[(df_campaign['Date'] >= start_date)
                          & (df_campaign['Date'] <= end_date)].copy()
    study_size = df_date.loc[df_date['Condition'] != 'None', 'Size'].unique(
    ).sum()
    lift_list = []
    control_list = []
    for i in conditions:
        if (i != 'None') & (i != 'Control'):
            df_subset = df_date[df_date['Condition'] == i].copy()
            lift = df_subset['Counts'].sum() / (df_subset['Size'].mean() /
                                                study_size)
            lift = lift.round().astype('int')
            lift_list.append(lift)
        if i == 'Control':
            df_subset = df_date[df_date['Condition'] == i].copy()
            lift = df_subset['Counts'].sum() / (df_subset['Size'].mean() /
                                                study_size)
            lift = lift.round().astype('int')
            control_list.append(lift)
    lift = (np.array(lift_list) -
            np.array(control_list)) / np.array(control_list)
    lift = (lift * 100).round().astype('int')
    lift_statement = ''
    index_num = 0
    for i in conditions:
        if (i != 'None') & (i != 'Control'):
            message = 'The lift for the {} campaign is {}%. '.format(
                i, lift[index_num])
            lift_statement = lift_statement + message
            index_num = +1
    return lift_statement

if __name__ == '__main__':
    app.run_server(debug=True)