"""
Debug script to investigate why specific patients aren't matching as PERFECT duplicates.
Run this script to see character-by-character comparison of the 13 problematic patients.
"""
import streamlit as st
import pandas as pd
import json
from google_sheets import authenticate_google_sheets, get_sheet_by_url, read_sheet_to_df
from utils import normalize, get_block_key

# The 13 patients to investigate
PROBLEM_PATIENTS = [
    "Panmati Subhashchandra Gupta",
    "Md.Tahsin Turful Shaikh",
    "SHADABRAZA",
    "Sadanand Ashok Papaiya",
    "Uma Tukaram Mahatre",
    "MONIKA CHACHAL DAS",
    "DEENDAYAL KORI",
    "Shreyas Pendbhaje",
    "Krishna Raju Pawar",
    "OMPRAKASH RAJPUT",
    "SURAJ MALI",
    "SAYED SHAIKH",
    "SUMANKUMARI DIVAKAR ROY"
]

def show_char_diff(val1, val2, label1="Daily", label2="Yearly"):
    """Show character-by-character difference between two values"""
    s1 = str(val1) if pd.notna(val1) else ""
    s2 = str(val2) if pd.notna(val2) else ""

    result = []
    result.append(f"  {label1}: '{s1}' (len={len(s1)})")
    result.append(f"  {label2}: '{s2}' (len={len(s2)})")
    result.append(f"  Normalized {label1}: '{normalize(s1)}'")
    result.append(f"  Normalized {label2}: '{normalize(s2)}'")
    result.append(f"  Match after normalize: {normalize(s1) == normalize(s2)}")

    # Show character codes for debugging hidden characters
    if normalize(s1) != normalize(s2):
        result.append(f"  {label1} char codes: {[ord(c) for c in s1]}")
        result.append(f"  {label2} char codes: {[ord(c) for c in s2]}")

    return "\n".join(result)

def find_patient_in_df(df, name_col, patient_name):
    """Find a patient by name (case-insensitive partial match)"""
    normalized_search = normalize(patient_name)
    matches = []

    for idx, row in df.iterrows():
        row_name = normalize(str(row.get(name_col, "")))
        # Check for exact match or partial match
        if row_name == normalized_search or normalized_search in row_name or row_name in normalized_search:
            matches.append((idx, row))

    return matches

st.title("🔍 Debug: Why Aren't These 13 Patients PERFECT Matches?")

# Load credentials
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    with open("credentials.json", "w") as f:
        json.dump(creds, f)
    st.success("✅ Credentials loaded from secrets")
    creds_ready = True
else:
    st.info("⚠️ Upload your service account JSON file")
    uploaded_file = st.file_uploader("Upload Google Service Account JSON", type=['json'])
    if uploaded_file:
        with open("credentials.json", "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("✅ Credentials loaded")
        creds_ready = True
    else:
        creds_ready = False

if creds_ready:
    yearly_url = st.text_input("Yearly Database Sheet URL",
        value="https://docs.google.com/spreadsheets/d/1cttQ0yx-kPtOVKTndceOs2pCAoRVpPMZvwHT61IVi5I/edit?gid=47580770#gid=47580770")
    daily_url = st.text_input("Daily Sheet URL",
        value="https://docs.google.com/spreadsheets/d/1OMgCU93Oq0KEFtgH4ikYEO09dW_-v0_kDv_2BZZFOVE/edit?gid=1848846662#gid=1848846662")

    if st.button("🔍 Analyze the 13 Problem Patients"):
        try:
            client = authenticate_google_sheets("credentials.json")

            st.info("Loading yearly database...")
            yearly_spreadsheet = get_sheet_by_url(client, yearly_url)
            df_yearly = read_sheet_to_df(yearly_spreadsheet.sheet1)
            st.success(f"✅ Loaded {len(df_yearly)} yearly records")

            st.info("Loading daily sheet...")
            daily_spreadsheet = get_sheet_by_url(client, daily_url)
            df_daily = read_sheet_to_df(daily_spreadsheet.sheet1)
            st.success(f"✅ Loaded {len(df_daily)} daily records")

            # The 4 columns user selected
            name_col = "Name of Patient"
            mobile_col = "Mobile Number"
            diag_col = "Confirmed Diagnosis"
            test_col = "Test Performed"

            st.subheader("📊 Column Analysis")
            st.write(f"Comparing: **{name_col}**, **{mobile_col}**, **{diag_col}**, **{test_col}**")

            st.subheader("🔎 Detailed Comparison for Each Patient")

            for patient_name in PROBLEM_PATIENTS:
                st.markdown(f"---\n### 👤 {patient_name}")

                # Find in daily
                daily_matches = find_patient_in_df(df_daily, name_col, patient_name)
                yearly_matches = find_patient_in_df(df_yearly, name_col, patient_name)

                if not daily_matches:
                    st.warning(f"❌ NOT FOUND in daily sheet")
                    continue

                if not yearly_matches:
                    st.warning(f"❌ NOT FOUND in yearly database - this is why it's not a duplicate!")
                    continue

                st.success(f"✅ Found {len(daily_matches)} in daily, {len(yearly_matches)} in yearly")

                # Compare first match from each
                daily_idx, daily_row = daily_matches[0]
                yearly_idx, yearly_row = yearly_matches[0]

                # Compare each column
                cols_data = [
                    (name_col, "Name"),
                    (mobile_col, "Mobile"),
                    (diag_col, "Confirmed Diagnosis"),
                    (test_col, "Test Performed")
                ]

                match_count = 0
                for col, label in cols_data:
                    daily_val = daily_row.get(col, "")
                    yearly_val = yearly_row.get(col, "")

                    daily_norm = normalize(daily_val)
                    yearly_norm = normalize(yearly_val)

                    is_match = daily_norm == yearly_norm
                    if is_match:
                        match_count += 1
                        st.markdown(f"**{label}**: ✅ MATCH")
                    else:
                        st.markdown(f"**{label}**: ❌ MISMATCH")

                    with st.expander(f"Details for {label}"):
                        st.code(show_char_diff(daily_val, yearly_val))

                # Summary
                if match_count == 4:
                    st.success(f"🟢 All 4 columns match - should be PERFECT!")
                else:
                    st.error(f"❌ Only {match_count}/4 columns match - NOT PERFECT")

        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())
