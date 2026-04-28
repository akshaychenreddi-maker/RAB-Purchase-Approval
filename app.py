import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------
# PAGE CONFIG
# ---------------------------
st.set_page_config(page_title="RAB Purchase Approval", layout="wide")

# ---------------------------
# STYLING
# ---------------------------
st.markdown("""
<style>
body { background-color: #f5f9fc; }
.title {
    text-align: center;
    font-size: 36px;
    font-weight: 800;
    color: #0c285d;
}
.stButton>button {
    background-color: #46275b;
    color: white;
    border-radius: 8px;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------
# HEADER
# ---------------------------
col1, col2, col3 = st.columns([1,2,1])

with col1:
    if st.button("HACHIAI X RAB DESIGN"):
        st.rerun()

with col2:
    st.markdown('<div class="title">RAB PURCHASE APPROVAL SYSTEM</div>', unsafe_allow_html=True)

st.markdown("---")

# ---------------------------
# GOOGLE SHEETS CONNECTION (CACHED)
# ---------------------------
@st.cache_resource
def connect_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    # ✅ ONLY CHANGE HERE (use secrets instead of file)
    creds_dict = st.secrets["gcp_service_account"]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        creds_dict, scope
    )

    client = gspread.authorize(creds)
    return client.open("RAB_Test").sheet1

sheet = connect_sheet()

# ---------------------------
# LOAD DATA (CACHED)
# ---------------------------
@st.cache_data
def load_data():
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    df.columns = df.columns.str.strip().str.lower()

    df = df.rename(columns={
        "suggested_quantity": "suggested_qty",
        "final_quantity": "approved_quantity"
    })

    df["approve"] = df.get("approve", 0)
    df["approve"] = df["approve"].apply(lambda x: 1 if str(x).lower() in ["true", "1"] else 0)

    df["approved_quantity"] = pd.to_numeric(df.get("approved_quantity", 0), errors="coerce").fillna(0)
    df["suggested_qty"] = pd.to_numeric(df.get("suggested_qty", 0), errors="coerce").fillna(0)
    df["current_stock"] = pd.to_numeric(df.get("current_stock", 0), errors="coerce").fillna(0)

    return df

df = load_data()

# ---------------------------
# BUYER FILTER
# ---------------------------
buyer = st.selectbox("Select Buyer", df["buyer"].unique())
filtered_df = df[df["buyer"] == buyer].copy()

# ---------------------------
# COLUMN ORDER (UPDATED)
# ---------------------------
filtered_df = filtered_df[
    ["id", "buyer", "sku", "description",
     "current_stock", "suggested_qty",
     "approved_quantity",
     "approve"]
]

# ---------------------------
# TABLE
# ---------------------------
edited_df = st.data_editor(
    filtered_df,
    use_container_width=True,
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "buyer": st.column_config.TextColumn("Buyer", disabled=True),
        "sku": st.column_config.TextColumn("SKU", disabled=True),
        "description": st.column_config.TextColumn("Description", disabled=True),
        "current_stock": st.column_config.NumberColumn("Current Stock", disabled=True),
        "suggested_qty": st.column_config.NumberColumn("Suggested Qty", disabled=True),
        "approved_quantity": st.column_config.NumberColumn("Approved Quantity"),
        "approve": st.column_config.CheckboxColumn("Approve"),
    }
)

# ---------------------------
# ONLY APPROVED ROWS COUNT
# ---------------------------
approved_rows = edited_df[edited_df["approve"] == 1]

# ---------------------------
# CHANGE DETECTION
# ---------------------------
changes_made = False

for _, row in approved_rows.iterrows():
    original = filtered_df[filtered_df["id"] == row["id"]].iloc[0]

    if str(row["approved_quantity"]) != str(original["approved_quantity"]) or int(original["approve"]) == 0:
        changes_made = True
        break

# ---------------------------
# SESSION STATE
# ---------------------------
if "confirm" not in st.session_state:
    st.session_state.confirm = False

# ---------------------------
# SUBMIT BUTTON
# ---------------------------
if st.button("Submit Approval"):

    if approved_rows.empty:
        st.warning("⚠️ Please select at least one row to approve.")
        st.stop()

    if not changes_made:
        st.warning("⚠️ No valid approved changes detected.")
        st.stop()

    st.session_state.confirm = True

# ---------------------------
# CONFIRMATION POPUP
# ---------------------------
if st.session_state.confirm:

    st.markdown("### Confirm Approval")

    st.dataframe(
        approved_rows[["sku", "approved_quantity"]],
        use_container_width=True
    )

    col1, col2 = st.columns(2)

    # ✅ CONFIRM
    with col1:
        if st.button("Yes, Submit"):

            with st.spinner("Updating..."):

                all_values = sheet.get_all_values()

                for i in range(1, len(all_values)):
                    row_id = int(all_values[i][0])

                    match = approved_rows[approved_rows["id"] == row_id]

                    if not match.empty:
                        all_values[i][7] = str(int(match.iloc[0]["approved_quantity"]))
                        all_values[i][6] = "1"

                sheet.update(all_values)

            st.success("✅ Data updated successfully!")
            st.session_state.confirm = False
            st.cache_data.clear()

    # ❌ CANCEL
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm = False
