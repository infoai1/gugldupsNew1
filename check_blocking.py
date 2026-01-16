"""
Debug script to check why patients aren't being found by blocking.
Run: streamlit run check_blocking.py
"""
import streamlit as st
import pandas as pd
import json
from google_sheets import authenticate_google_sheets, get_sheet_by_url, read_sheet_to_df
from utils import normalize, get_block_key, build_yearly_index, build_name_index

PROBLEM_PATIENTS = [
    "Affan Azizur.Rehman Mansoori",
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

st.title("🔍 Debug: Why Aren't Patients Being Found?")

# Load credentials
if "gcp_service_account" in st.secrets:
    creds = dict(st.secrets["gcp_service_account"])
    with open("credentials.json", "w") as f:
        json.dump(creds, f)
    creds_ready = True
else:
    uploaded_file = st.file_uploader("Upload Google Service Account JSON", type=['json'])
    if uploaded_file:
        with open("credentials.json", "wb") as f:
            f.write(uploaded_file.getbuffer())
        creds_ready = True
    else:
        creds_ready = False
        st.stop()

yearly_url = st.text_input("Yearly Database Sheet URL",
    value="https://docs.google.com/spreadsheets/d/1cttQ0yx-kPtOVKTndceOs2pCAoRVpPMZvwHT61IVi5I/edit?gid=47580770#gid=47580770")
daily_url = st.text_input("Daily Sheet URL",
    value="https://docs.google.com/spreadsheets/d/1OMgCU93Oq0KEFtgH4ikYEO09dW_-v0_kDv_2BZZFOVE/edit?gid=1848846662#gid=1848846662")

name_col = st.text_input("Name column", value="Name of Patient")
mobile_col = st.text_input("Mobile column", value="Mobile Number")

if st.button("🔍 Check Blocking for Problem Patients"):
    client = authenticate_google_sheets("credentials.json")

    st.info("Loading sheets...")
    yearly_spreadsheet = get_sheet_by_url(client, yearly_url)
    df_yearly = read_sheet_to_df(yearly_spreadsheet.sheet1)

    daily_spreadsheet = get_sheet_by_url(client, daily_url)
    df_daily = read_sheet_to_df(daily_spreadsheet.sheet1)

    st.success(f"Loaded {len(df_yearly)} yearly, {len(df_daily)} daily records")

    # Build indices
    yearly_blocks = build_yearly_index(df_yearly, mobile_col)
    name_blocks = build_name_index(df_yearly, name_col)

    st.write(f"**Mobile blocks:** {len(yearly_blocks)} unique last-4-digits")
    st.write(f"**Name blocks:** {len(name_blocks)} unique normalized names")

    st.subheader("🔎 Checking Each Problem Patient")

    for patient_name in PROBLEM_PATIENTS:
        st.markdown(f"---\n### 👤 {patient_name}")

        # Find in daily
        daily_match = None
        for idx, row in df_daily.iterrows():
            if normalize(row[name_col]) == normalize(patient_name):
                daily_match = (idx, row)
                break
            # Also try partial match
            if normalize(patient_name) in normalize(str(row[name_col])) or normalize(str(row[name_col])) in normalize(patient_name):
                daily_match = (idx, row)
                break

        if not daily_match:
            st.warning(f"❌ Not found in daily sheet")
            continue

        idx, daily_row = daily_match
        daily_name = daily_row[name_col]
        daily_mobile = daily_row[mobile_col]

        st.write(f"**Daily Name:** `{daily_name}`")
        st.write(f"**Daily Mobile:** `{daily_mobile}`")

        # Check mobile blocking
        mobile_key = get_block_key(daily_mobile)
        mobile_candidates = yearly_blocks.get(mobile_key, [])
        st.write(f"**Mobile Key (last 4):** `{mobile_key}` → {len(mobile_candidates)} candidates")

        # Check name blocking
        name_key = normalize(daily_name)
        name_candidates = name_blocks.get(name_key, [])
        st.write(f"**Name Key:** `{name_key}` → {len(name_candidates)} candidates")

        if len(mobile_candidates) == 0 and len(name_candidates) == 0:
            st.error("❌ NO CANDIDATES FOUND - This patient won't be matched!")

            # Try to find similar names in yearly
            st.write("**Looking for similar names in yearly...**")
            similar = []
            for _, yrow in df_yearly.iterrows():
                yearly_name_norm = normalize(yrow[name_col])
                if name_key[:10] in yearly_name_norm or yearly_name_norm[:10] in name_key:
                    similar.append(yrow[name_col])
            if similar:
                st.write(f"Similar names found: {similar[:5]}")
            else:
                st.write("No similar names found")
        else:
            st.success(f"✅ Found {len(mobile_candidates) + len(name_candidates)} total candidates")
