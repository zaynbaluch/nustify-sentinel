# app.py (Streamlit UI) with debug logs
import streamlit as st
from core.db import supabase
from core.scraper import scrape_page
from core.utils import get_text_hash
from core.analyzer import llm_analyze_change
from core.notifier import send_alert
from datetime import datetime

# ==============================
# Streamlit Config
# ==============================
st.set_page_config(page_title="Admissions Watch Pro", layout="wide")
st.title("🇵🇰 Admissions Watch Pro")

# --- Session state for safe reruns ---
if 'scan_trigger' not in st.session_state:
    st.session_state.scan_trigger = False

def trigger_scan():
    st.session_state.scan_trigger = not st.session_state.scan_trigger
    print("🔄 Scan triggered by user")

# --- Tabs ---
tab_feed, tab_sources, tab_subs = st.tabs(["📢 Feed", "🔗 Sources", "📧 Subscribers"])

# ==========================================
# 📢 FEED TAB
# ==========================================
with tab_feed:
    if st.button("🔄 Scan for Updates", on_click=trigger_scan):
        st.info("Scanning pages...")
        print("ℹ️ Manual scan button pressed")

    # Only run scan when triggered
    if st.session_state.scan_trigger:
        with st.spinner("Analyzing changes..."):
            sources = supabase.table("monitored_pages").select("*").execute().data or []
            print(f"📄 Found {len(sources)} monitored pages")

            for s in sources:
                st.write(f"Checking {s['name']}...")
                print(f"🔍 Scraping page: {s['url']}")
                content = scrape_page(s['url'])

                if not content:
                    st.warning(f"No content found for {s['name']}")
                    print(f"⚠️ No content retrieved from {s['url']}")
                    continue

                new_hash = get_text_hash(content)
                print(f"📝 New hash: {new_hash}")
                print(f"📝 Previous hash: {s['content_hash']}")

                if new_hash != s['content_hash']:
                    print("⚡ Content changed, calling LLM for analysis")
                    analysis = llm_analyze_change(s.get('last_content'), content)

                    if not isinstance(analysis, dict):
                        analysis = {"is_meaningful": False, "summary": ""}
                        print("❌ LLM returned invalid format, fallback applied")

                    print(f"🤖 LLM analysis: {analysis}")

                    if analysis.get('is_meaningful'):
                        db_summary = analysis['summary']
                        if isinstance(db_summary, list):
                            db_summary = "\n".join([f"• {item}" for item in db_summary])

                        print(f"✅ Meaningful change detected, saving to Supabase and sending alerts")
                        # Save to Supabase
                        supabase.table("detected_changes").insert({
                            "page_id": s['id'],
                            "title": s['name'],
                            "summary": db_summary,
                            "is_meaningful": True,
                            "url": s['url']
                        }).execute()

                        # Send alert safely
                        send_alert(s['name'], analysis['summary'], s['url'])
                    else:
                        print("ℹ️ Change not meaningful, skipping alert")

                    # Update hash & content
                    supabase.table("monitored_pages").update({
                        "last_content": content,
                        "content_hash": new_hash,
                        "last_checked": "now()"
                    }).eq("id", s['id']).execute()
                    print("💾 Updated page hash & content in Supabase")
                else:
                    print("ℹ️ No content change detected, skipping LLM call")

            st.success("Scan completed!")
            print("✅ Scan completed")

    # --- Display feed ---
    updates = supabase.table("detected_changes").select("*").eq("is_meaningful", True).order("timestamp", desc=True).execute().data or []
    for up in updates:
        status = "🆕" if not up['is_read'] else "✅"
        with st.expander(f"{status} {up['title']} - {up['timestamp'][:16]}"):
            st.markdown(up['summary'])
            if not up['is_read']:
                if st.button("Mark as Read", key=f"read_{up['id']}"):
                    supabase.table("detected_changes").update({"is_read": True}).eq("id", up['id']).execute()
                    st.session_state.scan_trigger = not st.session_state.scan_trigger
                    print(f"✔️ Marked {up['title']} as read")
            st.markdown(f"[View Source]({up['url']})")

# ==========================================
# 🔗 SOURCES TAB
# ==========================================
with tab_sources:
    st.subheader("Current Sources")
    sources = supabase.table("monitored_pages").select("id, name, url").execute().data or []
    print(f"📌 Sources tab loaded with {len(sources)} sources")

    for s in sources:
        c1, c2, c3 = st.columns([2, 5, 1])
        c1.write(s['name'])
        c2.write(s['url'])
        if c3.button("🗑️", key=f"del_{s['id']}"):
            print(f"🗑️ Deleting source: {s['name']}")
            supabase.table("detected_changes").delete().eq("page_id", s['id']).execute()
            supabase.table("monitored_pages").delete().eq("id", s['id']).execute()
            st.session_state.scan_trigger = not st.session_state.scan_trigger

    st.divider()
    
    st.subheader("Add New Source")
    with st.form("add_source_form", clear_on_submit=True):
        name = st.text_input("University Name")
        url = st.text_input("URL")
        if st.form_submit_button("Add Source"):
            if name and url:
                supabase.table("monitored_pages").insert({"name": name, "url": url}).execute()
                st.success(f"Added {name}!")
                print(f"➕ Added new source: {name} ({url})")
                st.session_state.scan_trigger = not st.session_state.scan_trigger
            else:
                st.warning("Both fields are required.")

# ==========================================
# 📧 SUBSCRIBERS TAB
# ==========================================
with tab_subs:
    st.subheader("Manage Subscribers")

    # --- List subscribers ---
    subs_list = supabase.table("email_subscribers").select("*").execute().data or []
    print(f"📬 Subscribers tab loaded with {len(subs_list)} subscribers")
    for sub in subs_list:
        col1, col2 = st.columns([4, 1])
        col1.write(sub['email'])
        if col2.button("Remove", key=f"rem_{sub['email']}"):
            supabase.table("email_subscribers").delete().eq("email", sub['email']).execute()
            st.session_state.scan_trigger = not st.session_state.scan_trigger
            print(f"🗑️ Removed subscriber: {sub['email']}")

    st.divider()

    # --- Add subscriber ---
    st.subheader("Add New Subscriber")
    with st.form("add_sub_form", clear_on_submit=True):
        email = st.text_input("Enter Email Address")
        if st.form_submit_button("Subscribe"):
            if "@" in email and "." in email:
                try:
                    supabase.table("email_subscribers").insert({"email": email}).execute()
                    st.success(f"{email} added!")
                    print(f"➕ Added new subscriber: {email}")
                    st.session_state.scan_trigger = not st.session_state.scan_trigger
                except:
                    st.error("This email might already be subscribed.")
                    print(f"⚠️ Failed to add subscriber: {email}")
            else:
                st.warning("Enter a valid email address.")
