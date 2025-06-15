
import streamlit as st
import pandas as pd
import pdfplumber
import yaml
import os

# Load users (in real SaaS this would be external DB)
USERS_FILE = "users.yaml"
with open(USERS_FILE) as f:
    users = yaml.safe_load(f)["users"]

# Simple login system
def login(username, password):
    if username in users and users[username]["password"] == password:
        return True, users[username]["name"]
    return False, None

# KnowledgeBase path (single shared KB for Phase 11 MVP)
KB_PATH = "output/CQA_KnowledgeBase_Master.csv"

# Ensure KB exists
if not os.path.exists(KB_PATH):
    os.makedirs("output", exist_ok=True)
    pd.DataFrame(columns=["Modality", "Phase", "CQA", "Test Methods", "Justification", "Regulatory Source", "Control Action"]).to_csv(KB_PATH, index=False)

# Load and save KnowledgeBase
def load_kb():
    return pd.read_csv(KB_PATH).fillna("")

def save_kb(df):
    df.to_csv(KB_PATH, index=False)

# Ingestion engine
def ingest_pdf(pdf_path, modality, phase):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    chunks = [text[i:i+1000] for i in range(0, len(text), 1000)]
    results = []
    for chunk in chunks:
        lower = chunk.lower()
        if modality.lower() in ["mab", "car-t", "fusion protein", "aav gene therapy", "adc"]:
            if "purity" in lower:
                results.append(("Purity", "HPLC, SEC"))
            if "potency" in lower:
                results.append(("Potency", "Bioassay, Cell-based Assay"))
            if "identity" in lower:
                results.append(("Identity", "Peptide Mapping"))
            if "glycosylation" in lower:
                results.append(("Glycosylation", "UPLC-MS"))
            if "charge variant" in lower or "icief" in lower:
                results.append(("Charge Variants", "iCIEF"))
            if "aggregation" in lower or "aggregate" in lower:
                results.append(("Aggregates", "SEC-HPLC"))
            if "oxidation" in lower:
                results.append(("Oxidation", "Peptide Mapping"))
        else:
            if "identity" in lower:
                results.append(("Identity", "HPLC RT, Mass Spec"))
            if "purity" in lower:
                results.append(("Purity", "HPLC, CE"))
            if "potency" in lower:
                results.append(("Potency", "Bioassay"))
            if "residual solvent" in lower:
                results.append(("Residual Solvents", "GC"))
            if "heavy metal" in lower:
                results.append(("Heavy Metals", "ICP-MS"))
            if "degradation" in lower:
                results.append(("Degradation Products", "Stability HPLC"))
            if "moisture" in lower:
                results.append(("Moisture Content", "Karl Fischer"))
            if "content uniformity" in lower:
                results.append(("Content Uniformity", "HPLC Assay"))
            if "polymorph" in lower:
                results.append(("Polymorphic Forms", "XRPD"))
    return results

# Reasoning engine
def query_reasoning(modality, phase, kb):
    df_filtered = kb[
        (kb['Modality'].str.lower() == modality.lower()) &
        (kb['Phase'].str.lower() == phase.lower())
    ]
    if df_filtered.empty:
        return "No data found for your query."
    grouped = df_filtered.groupby("CQA")
    output = []
    for cqa, group in grouped:
        tests = ", ".join(group["Test Methods"].unique())
        control_action = ", ".join(group["Control Action"].unique())
        justifications = ", ".join(group["Justification"].unique())
        output.append(f"**CQA:** {cqa}\n- Test Methods: {tests}\n- Control Action: {control_action}\n- Justification: {justifications}\n")
    return "\n\n".join(output)

# Streamlit UI with authentication
st.set_page_config(page_title="CMC Unified SaaS (Phase 11)", page_icon="🔐", layout="wide")
st.title("🔐 CMC Unified SaaS Platform (Phase 11)")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("User Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        success, name = login(username, password)
        if success:
            st.session_state.logged_in = True
            st.session_state.user = name
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")
else:
    st.success(f"Welcome, {st.session_state.user}!")
    menu = st.sidebar.radio("Navigate", ["📄 Ingest PDF", "🔎 Query Reasoning Agent", "📊 View KnowledgeBase", "🚪 Logout"])
    kb = load_kb()

    if menu == "📄 Ingest PDF":
        st.header("📄 Ingest New Regulatory PDF")
        uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
        modality = st.text_input("Modality (e.g., mAb, ADC, CAR-T, AAV Gene Therapy, Small Molecule)")
        phase = st.text_input("Phase (e.g., Phase 1, Phase 2, Phase 3)")
        if st.button("Ingest"):
            if uploaded_file and modality and phase:
                with open("uploaded.pdf", "wb") as f:
                    f.write(uploaded_file.read())
                new_results = ingest_pdf("uploaded.pdf", modality, phase)
                if new_results:
                    new_records = []
                    for cqa, test in new_results:
                        new_records.append({
                            "Modality": modality, "Phase": phase, "CQA": cqa,
                            "Test Methods": test, "Justification": "AI Extracted",
                            "Regulatory Source": "PDF-LLM", "Control Action": "Specification"
                        })
                    new_df = pd.DataFrame(new_records)
                    kb = pd.concat([kb, new_df], ignore_index=True)
                    save_kb(kb)
                    st.success(f"Ingestion complete. {len(new_df)} new records added!")
                else:
                    st.warning("No extractable data found in PDF.")
            else:
                st.warning("Please upload a PDF and fill modality and phase.")

    elif menu == "🔎 Query Reasoning Agent":
        st.header("🔎 Reasoning Agent")
        modality = st.selectbox("Select Modality", sorted(kb["Modality"].unique()))
        phase = st.selectbox("Select Phase", sorted(kb["Phase"].unique()))
        if st.button("Run Reasoning Query"):
            response = query_reasoning(modality, phase, kb)
            st.markdown(response)

    elif menu == "📊 View KnowledgeBase":
        st.header("📊 Current KnowledgeBase")
        st.dataframe(kb, use_container_width=True)
        st.download_button("Download KnowledgeBase CSV", kb.to_csv(index=False), file_name="CQA_KnowledgeBase_Master.csv")

    elif menu == "🚪 Logout":
        st.session_state.logged_in = False
        st.experimental_rerun()
