import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np

def authenticate_google_sheets(json_keyfile_path):
    """Authenticate with Google Sheets API"""
    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    
    creds = ServiceAccountCredentials.from_json_keyfile_name(json_keyfile_path, scope)
    client = gspread.authorize(creds)
    return client

def get_sheet_by_url(client, url):
    """Open sheet by URL"""
    return client.open_by_url(url)

def read_sheet_to_df(worksheet):
    """Read worksheet to pandas DataFrame"""
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def create_or_clear_sheet(spreadsheet, sheet_name):
    """Create new sheet or clear existing one"""
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        worksheet.clear()
        return worksheet
    except:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=30)
        return worksheet

def write_df_to_sheet(worksheet, df):
    """Write DataFrame to worksheet - handles NaN values"""
    # Replace NaN, None, inf with empty string
    df_clean = df.replace([np.nan, np.inf, -np.inf, None], '', regex=False)
    
    # Convert all values to strings to avoid JSON issues
    df_clean = df_clean.astype(str)
    
    # Replace 'nan' strings with empty strings
    df_clean = df_clean.replace('nan', '', regex=False)
    
    # Write to sheet
    worksheet.update([df_clean.columns.values.tolist()] + df_clean.values.tolist())

def delete_rows_by_indices(worksheet, row_indices, progress_callback=None):
    """Delete specific rows from worksheet with error handling"""
    import time

    # Sort in reverse to delete from bottom to top
    sorted_indices = sorted(row_indices, reverse=True)

    deleted_count = 0
    failed_indices = []

    for i, idx in enumerate(sorted_indices):
        try:
            # +2 because: +1 for header row, +1 for 1-based indexing
            worksheet.delete_rows(idx + 2)
            deleted_count += 1

            # Add small delay to avoid rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(1)  # Pause every 10 deletions

            if progress_callback:
                progress_callback(i + 1, len(sorted_indices))

        except Exception as e:
            failed_indices.append((idx, str(e)))
            # Continue trying other rows
            continue

    return {
        'deleted': deleted_count,
        'failed': len(failed_indices),
        'failed_details': failed_indices
    }
