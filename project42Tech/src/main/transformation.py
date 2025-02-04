import pandas as pd
import numpy as np
import psycopg2
from fuzzywuzzy import fuzz, process
import uuid
import config
import json

import os

# PostgreSQL database connection
def connect_db():
    return psycopg2.connect(
        dbname=config.DBNAME,
        user=config.USERNAME,
        password=config.PASSWORD,
        host=config.HOST,
        port=config.PORT
    )

# Use panda to read CSV and XLSX files
input_path = "src/resources/input"
csv_path = input_path + "/electricity-generation_emissions_sources_ownership.csv"
xlsx_path = input_path + "/Global-Nuclear-Power-Tracker-October-2023.xlsx"

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', 999)
# pd.set_option('display.width', 999)
# csv_data = pd.read_csv(csv_path)
# xlsx_data = pd.read_excel(xlsx_path, sheet_name="data")


def read_data(csv_path, xlsx_path):
    csv_data = pd.read_csv(csv_path)
    csv_data.rename(columns={"iso3_country":"country"}, inplace=True)
    xlsx_data = pd.read_excel(xlsx_path, sheet_name="Data")
    xlsx_data.rename(columns={"Owner":"company_name", "Latitude":"lat", "Construction Start Date":"start_date", "Longitude":"lon", "Retirement Date":"end_date", "Project Name":"asset", "GEM location ID":"indicator"}, inplace=True)
    return csv_data, xlsx_data

# company names normalisation
def normalize_company_name(name):
    return ' '.join(str(name).lower().strip().split())

# Unique ID generation
def generate_unique_id():
    return str(uuid.uuid4())

# Use fuzzy matching to match company names
def match_companies(name, company_list):
    match, score = process.extractOne(name, company_list, scorer=fuzz.token_sort_ratio)
    return match if score > 80 else name

# Insert data into PostgreSQL table
def load_to_postgresql(df, table_name, conn):
    cursor = conn.cursor()
    # Drop existing table
    cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
    
    # Create table query
    create_table_query = f'''
    CREATE TABLE {table_name} (
        surrogate_key UUID PRIMARY KEY,
        source_id TEXT,
        company_name TEXT,
        asset TEXT,
        indicator TEXT,
        
        metadata JSONB
    );
    '''
    cursor.execute(create_table_query)
    conn.commit()
    
    # Insert record into the table from df
    for index, row in df.iterrows():
        cursor.execute(
            f"INSERT INTO {table_name} (surrogate_key, source_id, company_name, asset, indicator, metadata) VALUES (%s, %s, %s, %s, %s, %s)",
            (generate_unique_id(), row['source_id'], row['company_name'], row['asset'], row['indicator'], json(row['metadata']))
        )
    conn.commit()

# Main ETL function
def etl_pipeline(csv_path, xlsx_path):
    csv_data, xlsx_data = read_data(csv_path, xlsx_path)
    
    # Combine data into a single dataframe
    combined_data = pd.concat([csv_data, xlsx_data], ignore_index=True)
    
    # Normalize company names
    combined_data['company_name'] = combined_data['company_name'].apply(normalize_company_name)
    
    # Generate unique IDs where missing
    combined_data['source_id'] = combined_data.apply(lambda row: generate_unique_id() if pd.isnull(row['source_id']) else row['source_id'], axis=1)
    
    # Perform fuzzy matching for company names
    unique_companies = combined_data['company_name'].unique()
    combined_data['company_name'] = combined_data['company_name'].apply(lambda x: match_companies(x, unique_companies))
    
    # Create metadata column
    combined_data['metadata'] = combined_data.apply(lambda row: {'source': 'csv' if row.name < len(csv_data) else 'xlsx'}, axis=1)

    return combined_data

conn = connect_db()

if __name__ == "__main__":
    load_to_postgresql(etl_pipeline(csv_path, xlsx_path), 'unified_42Tech_data', conn)
    
