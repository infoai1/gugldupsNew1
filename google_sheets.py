import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import numpy as np
import time

def retry_on_quota(func, max_retries=3, initial_delay=30):
    """Decorator/wrapper to retry on quota errors"""
    def wrapper(*args, **kwargs):
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_str = str(e).lower()
                if '429' in str(e) or 'quota' in error_str or 'rate' in error_str:
                    if attempt < max_retries - 1:
                        wait_time = initial_delay * (attempt + 1)
                        print(f"Rate limited. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                    else:
                        raise Exception(f"Rate limit exceeded after {max_retries} retries: {e}")
                else:
                    raise
        return None
    return wrapper

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
    """Create new sheet or clear existing one with rate limit handling"""
    for attempt in range(3):
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
            time.sleep(2)  # Delay after clear operation
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=30)
            time.sleep(2)  # Delay after create operation
            return worksheet
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower():
                wait_time = 60  # Wait full minute for quota reset
                print(f"Rate limited on create/clear. Waiting {wait_time}s for quota reset...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Failed to create/clear sheet after retries")

def write_df_to_sheet(worksheet, df):
    """Write DataFrame to worksheet - handles NaN values with rate limit handling"""
    # Replace NaN, None, inf with empty string
    df_clean = df.replace([np.nan, np.inf, -np.inf, None], '', regex=False)

    # Convert all values to strings to avoid JSON issues
    df_clean = df_clean.astype(str)

    # Replace 'nan' strings with empty strings
    df_clean = df_clean.replace('nan', '', regex=False)

    # Write to sheet with retry logic
    data = [df_clean.columns.values.tolist()] + df_clean.values.tolist()

    for attempt in range(3):
        try:
            worksheet.update(data)
            time.sleep(5)  # Delay after write to avoid rate limit
            return
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower():
                wait_time = 60  # Wait full minute for quota reset
                print(f"Rate limited on write. Waiting {wait_time}s for quota reset...")
                time.sleep(wait_time)
            else:
                raise
    raise Exception("Failed to write to sheet after retries")

def delete_rows_by_indices(worksheet, row_indices, progress_callback=None):
    """Delete specific rows from worksheet with rate limit handling"""
    # Sort in reverse to delete from bottom to top
    sorted_indices = sorted(row_indices, reverse=True)

    deleted_count = 0
    failed_indices = []

    for i, idx in enumerate(sorted_indices):
        max_retries = 3

        for attempt in range(max_retries):
            try:
                # +2 because: +1 for header row, +1 for 1-based indexing
                worksheet.delete_rows(idx + 2)
                deleted_count += 1

                # Delay 2 seconds after each deletion to stay under rate limit (30 deletes/min)
                time.sleep(2)

                if progress_callback:
                    progress_callback(i + 1, len(sorted_indices))

                break  # Success

            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'quota' in error_str.lower():
                    if attempt < max_retries - 1:
                        # Wait 60 seconds for quota to fully reset
                        wait_time = 60
                        if progress_callback:
                            progress_callback(i + 1, len(sorted_indices), f"Rate limited, waiting {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        failed_indices.append((idx, "Rate limit exceeded"))
                else:
                    failed_indices.append((idx, error_str))
                    break

    return {
        'deleted': deleted_count,
        'failed': len(failed_indices),
        'failed_details': failed_indices
    }
