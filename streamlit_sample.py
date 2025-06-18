import streamlit as st
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


FASTAPI_PRESIGN_URL = "https://zazzes27ai.execute-api.ap-south-1.amazonaws.com/prod/generate-presigned-url/"
FASTAPI_SAVE_POLICY_URL = "https://zazzes27ai.execute-api.ap-south-1.amazonaws.com/prod/save-policy/"
FASTAPI_LIST_POLICIES_URL = "https://zazzes27ai.execute-api.ap-south-1.amazonaws.com/prod/policies/"
FASTAPI_GET_PAYOR_URL = "https://zazzes27ai.execute-api.ap-south-1.amazonaws.com/prod/payors/"

# @st.cache_data
def get_payors():
    try:
        response = requests.get(FASTAPI_GET_PAYOR_URL)
        response.raise_for_status()
        payors_data = response.json()
        # Build dict: {payor_name: payor_id}
        logger.info(f"Payors data: {payors_data}")
        return {payor['name']: payor['id'] for payor in payors_data}
    except Exception as e:
        st.error(f"Failed to fetch payors: {e}")
        return {}
    
# Loading payors once
PAYORS = get_payors()


# Create two tabs
tab1, tab2 = st.tabs(["📤 Upload Policy", "📑 View Policies"])

# ---------------------------------------------
# TAB 1: Upload
with tab1:
    st.header("Upload Policy Document")

    selected_payor = st.selectbox("Select a Payor", ["-- Select --"] + list(PAYORS.keys()), key="upload_payor")

    if selected_payor != "-- Select --":
        st.success(f"Payor selected: {selected_payor}")
        payor_id = PAYORS[selected_payor]
        print(f"Payor ID: {payor_id}")

        uploaded_file = st.file_uploader("Upload Policy PDF", type=["pdf"], key="upload_pdf")

        if uploaded_file is not None:
            st.write(f"Uploading `{uploaded_file.name}` for `{selected_payor}`...")

            presign_payload = {
                "file_name": f"{selected_payor}_{uploaded_file.name}",
                "content_type": "application/pdf"
            }

            try:
                presign_response = requests.post(FASTAPI_PRESIGN_URL, json=presign_payload)
                presign_result = presign_response.json()

                if "upload_url" in presign_result:
                    upload_url = presign_result["upload_url"]
                    s3_key = presign_result["s3_key"]

                    upload_response = requests.put(
                        upload_url,
                        data=uploaded_file.getvalue(),
                        headers={"Content-Type": "application/pdf"}
                    )

                    if upload_response.status_code == 200:
                        st.success(f"✅ Uploaded to S3: `{s3_key}`")

                        save_policy_payload = {
                            "payor_id": str(payor_id),
                            "document_s3_key": s3_key
                        }

                        save_response = requests.post(FASTAPI_SAVE_POLICY_URL, json=save_policy_payload)
                        save_result = save_response.json()

                        if save_response.status_code == 200:
                            st.success("📄 Metadata saved to DB successfully.")
                            st.json(save_result)
                        else:
                            st.error(f"❌ Failed to save metadata: {save_result.get('detail', 'Unknown error')}")
                    else:
                        st.error(f"❌ Upload to S3 failed. Status code: {upload_response.status_code}")
                else:
                    st.error(f"❌ Could not generate presigned URL: {presign_result.get('error', 'Unknown error')}")

            except Exception as e:
                st.error(f"❌ Unexpected error: {e}")

# ---------------------------------------------
# TAB 2: View Policies
with tab2:
    st.header("View Existing Policies")

    view_payor = st.selectbox("Choose a Payor", ["-- Select --"] + list(PAYORS.keys()), key="view_payor")

    if view_payor != "-- Select --":
        payor_id = PAYORS[view_payor]

        try:
            response = requests.get(FASTAPI_LIST_POLICIES_URL, params={"payor_id": payor_id})
            if response.status_code == 200:
                policies = response.json()

                if not policies:
                    st.warning("No policies found for this payor.")
                else:
                    options = {f"📄 {p['document_url']}": p for p in policies}
                    selected_policy_label = st.selectbox("Select a Policy", list(options.keys()))
                    selected_policy = options[selected_policy_label]

                    st.markdown("### Policy Info")
                    st.write(f"**Document URL:** {selected_policy['document_url']}")
                    st.write(f"**Created At:** {selected_policy.get('created_at', 'N/A')}")
                    st.markdown(f"[🔗 Open in S3]({selected_policy['document_url']})", unsafe_allow_html=True)
            else:
                st.error("Failed to fetch policies.")
        except Exception as e:
            st.error(f"Error fetching policies: {e}")
