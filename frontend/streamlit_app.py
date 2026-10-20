"""Streamlit dashboard that delegates all processing to FastAPI."""

import streamlit as st

from frontend.api_client import (
    ask_question,
    delete_document,
    get_documents,
    get_document,
    get_health,
    get_integrity,
    ingest_folder,
    upload_pdf,
    verify_document,
)

st.set_page_config(page_title="Verified Compliance RAG", page_icon="📄")
st.title("Cryptography-Anchored RAG Compliance System")

try:
    health = get_health()
    documents = get_documents()
except Exception as error:
    st.error(f"The backend is unavailable: {error}")
    st.stop()

st.header("Dashboard")
status_columns = st.columns(3)
status_columns[0].metric("Backend", health["status"])
status_columns[1].metric("Active documents", len(documents))
status_columns[2].metric(
    "Indexed chunks", sum(document.get("chunk_count", 0) for document in documents)
)
st.json(health["dependencies"])
if documents:
    st.dataframe(
        [
            {
                "Document": document["filename"],
                "Version": document["version"],
                "Chunks": document["chunk_count"],
            }
            for document in documents
        ],
        hide_index=True,
        use_container_width=True,
    )

st.header("Upload and ingest")
uploaded_file = st.file_uploader("Choose a PDF", type=["pdf"])
if st.button("Upload and index PDF", disabled=uploaded_file is None):
    try:
        with st.spinner("Extracting text, building indexes, and signing the root..."):
            result = upload_pdf(uploaded_file.name, uploaded_file.getvalue())
        st.success("PDF ingested.")
        st.json(result)
        st.rerun()
    except Exception as error:
        st.error(str(error))

if st.button("Ingest PDFs from configured folder"):
    try:
        with st.spinner("Ingesting configured PDF folder..."):
            result = ingest_folder()
        st.success(f"Processed {len(result['documents'])} PDF file(s).")
        st.json(result["documents"])
        st.rerun()
    except Exception as error:
        st.error(str(error))

st.header("Ask a question")
question = st.text_area("Compliance question")
if st.button("Search and answer", disabled=not question.strip()):
    try:
        with st.spinner("Searching, verifying, and preparing an answer..."):
            result = ask_question(question.strip())
        st.subheader("Answer")
        st.write(result["answer"])
        if result["verified"]:
            st.success("Answer was generated from verified evidence.")
        elif not result["sources"]:
            st.info("Sufficient evidence was not found. No LLM call was made.")
        st.subheader("Sources")
        if result["sources"]:
            st.table(result["sources"])
    except Exception as error:
        st.error(str(error))

st.header("Integrity checker")
if documents:
    selected_document = st.selectbox(
        "Select a document",
        documents,
        format_func=lambda item: f"{item['filename']} ({item['version'][:12]})",
        key="integrity_document",
    )
    try:
        document_details = get_document(selected_document["document_id"])
        versions = document_details.get("versions", [])
    except Exception as error:
        versions = []
        st.error(f"Could not load document versions: {error}")

    selected_version = None
    if versions:
        selected_version = st.selectbox(
            "Select a document version",
            versions,
            format_func=lambda item: (
                f"{item['version'][:12]} ({'active' if item['active'] else 'inactive'})"
            ),
            key="integrity_version",
        )

    integrity_columns = st.columns(2)
    if integrity_columns[0].button(
        "Inspect integrity", disabled=selected_version is None
    ):
        try:
            st.json(
                get_integrity(
                    selected_document["document_id"], selected_version["version"]
                )
            )
        except Exception as error:
            st.error(str(error))
    if integrity_columns[1].button(
        "Verify all chunks", disabled=selected_version is None
    ):
        try:
            integrity_result = verify_document(
                selected_document["document_id"], selected_version["version"]
            )
            if integrity_result["integrity_valid"]:
                if integrity_result["active_version"]:
                    st.success("Manifest, hashes, and Merkle proofs passed.")
                else:
                    st.info(
                        "This inactive version is intact but is not used for answers."
                    )
            else:
                st.error(integrity_result["message"])
            st.json(integrity_result)
        except Exception as error:
            st.error(str(error))

    if st.button("Deactivate selected document"):
        try:
            st.success(delete_document(selected_document["document_id"])["message"])
            st.rerun()
        except Exception as error:
            st.error(str(error))
else:
    st.info("Upload or ingest a PDF to see document integrity details.")
