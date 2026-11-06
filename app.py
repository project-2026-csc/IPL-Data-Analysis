import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import mysql.connector
from mysql.connector import Error
from pathlib import Path

st.set_page_config(page_title='IPL Data Analysis', page_icon='🏏', layout='wide')
DATA_FILE = Path(__file__).parent / 'data' / 'ipl_comprehensive_dataset.csv'
TABLE = 'ipl_matches'

@st.cache_data
def load_csv():
    df = pd.read_csv(DATA_FILE)
    for col in ['season', 'match_number', 'team1_runs', 'team1_wickets', 'team2_runs', 'team2_wickets', 'win_by_runs', 'win_by_wickets', 'overs_limit']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df

def get_connection(host, port, user, password, database):
    return mysql.connector.connect(host=host, port=int(port), user=user, password=password, database=database)

def sql_safe(value):
    if pd.isna(value): return None
    return str(value)

def create_and_import(conn, df):
    cur = conn.cursor()
    definitions = []
    numeric = {'season','match_number','team1_runs','team1_wickets','team2_runs','team2_wickets','win_by_runs','win_by_wickets','overs_limit','balls_per_over'}
    for c in df.columns:
        if c in numeric:
            definitions.append(f'`{c}` DOUBLE NULL')
        else:
            definitions.append(f'`{c}` TEXT NULL')
    cur.execute(f"CREATE TABLE IF NOT EXISTS `{TABLE}` (id INT AUTO_INCREMENT PRIMARY KEY, {', '.join(definitions)})")
    cols = list(df.columns)
    names = ','.join(f'`{c}`' for c in cols)
    placeholders = ','.join(['%s'] * len(cols))
    cur.execute(f'TRUNCATE TABLE `{TABLE}`')
    query = f'INSERT INTO `{TABLE}` ({names}) VALUES ({placeholders})'
    rows = [tuple(sql_safe(v) for v in row) for row in df[cols].itertuples(index=False, name=None)]
    cur.executemany(query, rows)
    conn.commit()
    cur.close()
    return len(rows)

st.title('🏏 IPL Data Analysis (2008–2026)')
st.caption('A Python dashboard using Pandas, Matplotlib and MySQL')

with st.sidebar:
    st.header('MySQL Connection')
    host = st.text_input('Host', value='localhost')
    port = st.number_input('Port', min_value=1, max_value=65535, value=3306)
    user = st.text_input('Username', value='root')
    password = st.text_input('Password', type='password')
    database = st.text_input('Database name', value='ipl_database')
    connect = st.button('Connect & import CSV to MySQL', type='primary')
    st.caption('For an online MySQL provider, enter its host, port, username, password and database here.')

if not DATA_FILE.exists():
    st.error('Dataset file is missing. Keep ipl_comprehensive_dataset.csv inside the data folder.')
    st.stop()

df = load_csv()
if connect:
    try:
        conn = get_connection(host, port, user, password, database)
        count = create_and_import(conn, df)
        conn.close()
        st.success(f'Successfully imported {count:,} IPL match records into MySQL table `{TABLE}`.')
    except Error as e:
        st.error(f'MySQL connection/import failed: {e}')

# Dashboard uses the supplied CSV for immediate display; MySQL import enables database storage.
st.info('Dashboard preview is loaded from your uploaded CSV. Use the MySQL panel to store the same records in your database.')

c1, c2, c3, c4 = st.columns(4)
c1.metric('Total matches', f'{len(df):,}')
c2.metric('Seasons', int(df['season'].nunique()))
c3.metric('Teams', int(pd.concat([df.team1, df.team2]).nunique()))
c4.metric('Venues', int(df['venue'].nunique()))

st.subheader('Explore matches')
seasons = sorted(df['season'].dropna().unique().tolist())
selected = st.selectbox('Choose season', ['All seasons'] + [str(int(x)) for x in seasons])
view = df if selected == 'All seasons' else df[df.season == int(selected)]
team_options = sorted(set(view.team1.dropna()) | set(view.team2.dropna()))
team = st.selectbox('Filter by team', ['All teams'] + team_options)
if team != 'All teams':
    view = view[(view.team1 == team) | (view.team2 == team)]
st.write(f'**Showing {len(view):,} matches**')
show_cols = [c for c in ['date','season','city','team1','team2','winner','win_by_runs','win_by_wickets','player_of_match'] if c in view.columns]
st.dataframe(view[show_cols], use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.subheader('Matches by season')
    counts = df.groupby('season').size().sort_index()
    fig, ax = plt.subplots()
    counts.plot(kind='bar', ax=ax)
    ax.set_xlabel('Season'); ax.set_ylabel('Number of matches'); ax.tick_params(axis='x', rotation=45)
    st.pyplot(fig); plt.close(fig)
with right:
    st.subheader('Top winning teams')
    wins = df[df.winner.notna() & (df.winner != 'No result')].winner.value_counts().head(10).sort_values()
    fig, ax = plt.subplots()
    wins.plot(kind='barh', ax=ax)
    ax.set_xlabel('Wins'); ax.set_ylabel('Team')
    st.pyplot(fig); plt.close(fig)

st.subheader('Top players of the match')
players = df['player_of_match'].dropna().value_counts().head(10).rename_axis('Player').reset_index(name='Awards')
st.dataframe(players, use_container_width=True, hide_index=True)

st.download_button('Download filtered match data (CSV)', data=view.to_csv(index=False).encode('utf-8'), file_name='ipl_filtered_matches.csv', mime='text/csv')
st.caption('Note: The supplied dataset contains 1,243 match records. Results reflect the contents of that file.')
